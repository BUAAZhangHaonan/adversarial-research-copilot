"""Offline evaluation orchestration tests; no service or quality claims."""
from __future__ import annotations

import json
import pytest

from arc.budget import BudgetLedger
from arc.config import Settings
from arc.evaluation import run_comparison, run_e2e
from tests.test_selection import research_store, research_draft, selection_result
from tests.test_workflows import ScriptedRuntime


class ComparisonRuntime(ScriptedRuntime):
    def __init__(self, store, calls, *, stop=False, invalid=False, needs=False, fail=False, missing_judgment=False):
        super().__init__(store, request_evidence=needs)
        self.calls=calls
        self.stop=stop
        self.invalid=invalid
        self.fail=fail
        self.missing_judgment=missing_judgment

    async def close(self):
        pass

    def reply(self, role, task, payload, task_id):
        if self.fail and task=='COMPOSE':
            raise RuntimeError('synthetic interrupted composition')
        if task=='NEXT_DRAW':
            return {'continue_or_stop':'STOP' if self.stop else 'CONTINUE',
                'proposed_family':None if self.stop else 'Controlled causal intervention',
                'anchor_evidence_ids':[] if self.stop else ['ev_synthetic'],
                'distinct_from_retained':None if self.stop else 'Separates the two factors.',
                'relevant_archive_relations':[], 'missing_information':[],
                'why_this_draw_is_worthwhile':None if self.stop else 'A discriminating experiment.'}
        if role=='selector' and self.invalid:
            result=selection_result().model_dump(mode='json')
            result['selection_checks']['knowledge_delta']['status']='not_applicable'
            return result
        if role=='evaluator':
            return {'per_candidate_findings':[{'candidate_id':c['candidate_id'],
                'findings':['Synthetic comparison only.'], 'evidence_ids':[]} for c in
                ([] if self.missing_judgment else payload['candidates'])],
                'decisive_errors':[], 'supported_strengths':[], 'unresolved_verifications':[],
                'preference_if_requested':None, 'uncertainty':'No expert label or true model result.'}
        return super().reply(role,task,payload,task_id)


def environment(tmp_path, monkeypatch, *, boundaries=None, **runtime_options):
    import arc.cli
    import arc.bootstrap
    store,_,_=research_store(tmp_path)
    ledger=BudgetLedger(store.db_path)
    settings=Settings(data_dir=tmp_path/'evaluation')
    settings.data_dir.mkdir()
    monkeypatch.setattr(arc.cli,'services',lambda _: (store,ledger))
    calls=[]
    async def make_runtime(store, ledger, run, settings):
        return ComparisonRuntime(store,calls,**runtime_options)
    monkeypatch.setattr(arc.bootstrap,'make_runtime',make_runtime)
    campaign=store.create_campaign('Controlled recall mechanisms',boundaries=boundaries)
    source=store.create_run('discover',campaign_id=campaign.campaign_id,
        state={'source_ids':['src_synthetic'],'evidence_ids':['ev_synthetic']})
    return settings,store,source,calls


@pytest.mark.asyncio
async def test_comparison_uses_identical_frozen_material_and_persists_judgments(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch)
    report=await run_comparison(settings,source.run_id)
    assert report['comparison_status']=='completed'
    assert all(not c['tools'] for c in calls)
    compose=[c['payload'] for c in calls if c['task']=='COMPOSE']
    assert compose[0]['evidence']==compose[1]['evidence']
    assert compose[0]['sources']==compose[1]['sources']
    assert 'SYNTHETIC TEST SOURCE' in compose[0]['sources'][0]['content']
    for candidate in report['candidates']:
        run=store.get_run(source.run_id+'.comparison.'+candidate['system'])
        assert store.get_card(run.card_id,run.card_version).selection_result.selection=='MAIN_REPORT'
        assert candidate['cost']['limit_cny']=='20.000000'
    evaluator=[c for c in calls if c['role']=='evaluator'][0]
    assert all(set(c)=={'candidate_id','research_card'} for c in evaluator['payload']['candidates'])


@pytest.mark.asyncio
async def test_comparison_freezes_boundaries_for_every_stage_and_records_actual_shuffle_seed(tmp_path,monkeypatch):
    import arc.evaluation
    boundaries=['Use fixed training data; do not add labels.', 'Separate retrieval quality from reasoning accuracy.']
    settings,store,source,calls=environment(tmp_path,monkeypatch,boundaries=boundaries)
    actual_seeds=[]
    original_shuffle=arc.evaluation.anonymous_candidates
    def capture_shuffle(candidates,seed):
        actual_seeds.append(seed)
        return original_shuffle(candidates,seed=seed)
    monkeypatch.setattr(arc.evaluation,'anonymous_candidates',capture_shuffle)
    report=await run_comparison(settings,source.run_id)
    assert report['comparison_status']=='completed'
    assert len(calls)==9
    assert all(call['payload']['boundaries']==boundaries for call in calls)
    assert len([call for call in calls if '.ARC.' in call['task_id']])==5
    assert len([call for call in calls if '.direct-Pro.' in call['task_id']])==3
    assert len([call for call in calls if call['role']=='evaluator'])==1
    frozen=store.read_artifact(f'evaluations/{source.run_id}/evidence.json')
    assert json.loads(frozen)['material']['boundaries']==boundaries
    saved=json.loads(store.read_artifact(f'evaluations/{source.run_id}/comparison.json'))
    assert actual_seeds==[report['shuffle_seed']]==[saved['shuffle_seed']]
    count=len(calls)
    resumed=await run_comparison(settings,source.run_id)
    assert len(calls)==count
    assert resumed['shuffle_seed']==report['shuffle_seed']
    assert resumed['identity_map_private']==report['identity_map_private']
    assert store.read_artifact(f'evaluations/{source.run_id}/evidence.json')==frozen


@pytest.mark.asyncio
async def test_comparison_rejects_boundaryless_snapshot_without_rewriting_or_calling(tmp_path,monkeypatch):
    import hashlib
    from arc.validation import ProtocolViolation
    settings,store,source,calls=environment(tmp_path,monkeypatch,boundaries=['An explicit original boundary.'])
    material={'topic':store.get_campaign(source.campaign_id).topic,
        'sources':[store.get_record('src_synthetic')], 'evidence':[store.get_record('ev_synthetic')]}
    original=json.dumps({'material':material,'sha256':hashlib.sha256(json.dumps(material,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()},ensure_ascii=False)
    path=f'evaluations/{source.run_id}/evidence.json'
    store.save_artifact(path,original)
    with pytest.raises(ProtocolViolation,match='COMPARISON_MATERIAL_PROTOCOL_MISMATCH_MISSING_BOUNDARIES'):
        await run_comparison(settings,source.run_id)
    assert calls==[]
    assert store.read_artifact(path)==original


@pytest.mark.asyncio
async def test_comparison_resume_keeps_original_material_after_source_run_changes(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch,fail=True)
    first=await run_comparison(settings,source.run_id)
    assert first['comparison_status']=='incomplete'
    assert all(c['status']=='ERROR' for c in first['candidates'])
    original=store.read_artifact(f'evaluations/{source.run_id}/evidence.json')
    store.update_run(source.run_id,state={'source_ids':[],'evidence_ids':[]})
    import arc.bootstrap
    async def repaired(store, ledger, run, settings):
        return ComparisonRuntime(store,calls)
    monkeypatch.setattr(arc.bootstrap,'make_runtime',repaired)
    second=await run_comparison(settings,source.run_id)
    assert second['comparison_status']=='completed'
    assert second['material_hash']==first['material_hash']
    assert store.read_artifact(f'evaluations/{source.run_id}/evidence.json')==original
    assert len([c for c in calls if c['task']=='FRAME'])==1
    assert all(c['payload']['evidence'] for c in calls if c['task']=='COMPOSE')
    count=len(calls)
    await run_comparison(settings,source.run_id)
    assert len(calls)==count


@pytest.mark.asyncio
async def test_comparison_rejects_changed_frozen_material_before_any_new_call(tmp_path,monkeypatch):
    from arc.validation import ProtocolViolation
    settings,store,source,calls=environment(tmp_path,monkeypatch)
    await run_comparison(settings,source.run_id)
    path=f'evaluations/{source.run_id}/evidence.json'
    saved=json.loads(store.read_artifact(path))
    saved['material']['topic']='Silently changed topic'
    store.save_artifact(path,json.dumps(saved))
    count=len(calls)
    with pytest.raises(ProtocolViolation,match='COMPARISON_MATERIAL_HASH_MISMATCH'):
        await run_comparison(settings,source.run_id)
    assert len(calls)==count


@pytest.mark.asyncio
async def test_comparison_stop_produces_no_arc_card_and_never_composes_it(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch,stop=True)
    report=await run_comparison(settings,source.run_id)
    arc=report['candidates'][0]
    assert arc['draft'] is None and arc['stop_reason']=='no_distinct_direction'
    assert not any(c['task']=='COMPOSE' and '.ARC.' in c['task_id'] for c in calls)
    assert report['comparison_status']=='completed'


@pytest.mark.asyncio
async def test_comparison_rejects_semantically_unestablished_main_selection(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch,invalid=True)
    report=await run_comparison(settings,source.run_id)
    assert report['comparison_status']=='incomplete'
    assert all(c['status']=='PAUSED_PROTOCOL' and c['judgment'] is None for c in report['candidates'])
    assert not any(c['role']=='evaluator' for c in calls)
    assert all(card.selection_result is None for card in store.list_cards())


@pytest.mark.asyncio
async def test_evaluator_cannot_omit_candidate_judgments_and_report_completion(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch,missing_judgment=True)
    report=await run_comparison(settings,source.run_id)
    assert report['comparison_status']=='incomplete'
    assert report['evaluator_status']=='PAUSED_PROTOCOL'
    assert report['evaluation'] is None


@pytest.mark.asyncio
async def test_frozen_needs_evidence_is_saved_without_online_expansion_or_repeated_call(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch,needs=True)
    report=await run_comparison(settings,source.run_id)
    assert report['comparison_status']=='incomplete'
    assert all(c['status']=='PAUSED_EXTERNAL' and c['pending_envelopes'] for c in report['candidates'])
    assert not any(c['role'] in ('investigator','evaluator') for c in calls)
    count=len(calls)
    await run_comparison(settings,source.run_id)
    assert len(calls)==count


@pytest.mark.asyncio
@pytest.mark.parametrize('final_assessment',['PROMISING','REJECTED','NEEDS_EVIDENCE'])
async def test_same_card_final_scientific_assessment_does_not_erase_l3_completion(tmp_path,monkeypatch,final_assessment):
    import arc.cli
    settings,store,source,calls=environment(tmp_path,monkeypatch)
    card=store.save_card(research_draft())
    executed=[]
    async def execute(settings,run_id):
        run=store.get_run(run_id)
        executed.append(run.mode)
        if run.mode=='discover':
            state={'draws':{'draw1':{'card_id':card.card_id,'card_version':card.version,
                'selection':{'selection':'MAIN_REPORT'}}}}
            return store.update_run(run_id,status='COMPLETED',state=state)
        assert run.card_id==card.card_id
        return store.update_run(run_id,status='COMPLETED',
            assessment='PROMISING' if run.mode=='develop' else final_assessment)
    monkeypatch.setattr(arc.cli,'execute',execute)
    report=await run_e2e(settings,'synthetic','Controlled recall mechanisms','100')
    assert executed==['discover','develop','run']
    assert report['L3']=='natural_card_chain_completed'
    assert report['assessment']==final_assessment


@pytest.mark.asyncio
async def test_develop_rejection_does_not_force_pressure_test(tmp_path,monkeypatch):
    import arc.cli
    settings,store,source,calls=environment(tmp_path,monkeypatch)
    card=store.save_card(research_draft())
    executed=[]
    async def execute(settings,run_id):
        run=store.get_run(run_id)
        executed.append(run.mode)
        return store.update_run(run_id,status='COMPLETED',assessment='REJECTED' if run.mode=='develop' else None,
            state={'draws':{'draw1':{'card_id':card.card_id,'card_version':card.version,
                                    'selection':{'selection':'MAIN_REPORT'}}}})
    monkeypatch.setattr(arc.cli,'execute',execute)
    report=await run_e2e(settings,'synthetic','Controlled recall mechanisms','100')
    assert executed==['discover','develop']
    assert report['L3']=='stopped_at_develop'


@pytest.mark.asyncio
async def test_e2e_existing_campaign_rejects_different_topic_before_any_execution(tmp_path,monkeypatch):
    import arc.cli
    from arc.evaluation import VALIDATION_PARENT
    settings,store,source,calls=environment(tmp_path,monkeypatch)
    ledger=BudgetLedger(store.db_path)
    ledger.create_account(VALIDATION_PARENT,'100')
    run=arc.cli.new_run(settings,'discover',topic='Original controlled recall question',
        parent=VALIDATION_PARENT,run_id=f'{VALIDATION_PARENT}.synthetic.discover')
    original_campaign=store.get_campaign(run.campaign_id).model_dump(mode='json')
    original_run=run.model_dump(mode='json')
    executed=[]
    async def execute(settings,run_id):
        executed.append(run_id)
        raise AssertionError('Mismatched topic must fail before execute')
    monkeypatch.setattr(arc.cli,'execute',execute)
    with pytest.raises(ValueError,match='E2E_CAMPAIGN_TOPIC_MISMATCH'):
        await run_e2e(settings,'synthetic','A different research question','100')
    assert executed==[] and calls==[]
    assert store.get_campaign(run.campaign_id).model_dump(mode='json')==original_campaign
    assert store.get_run(run.run_id).model_dump(mode='json')==original_run


@pytest.mark.asyncio
async def test_original_question_and_frame_mandate_reach_compose_and_both_judges(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch,boundaries=['Preserve the user condition.'])
    await run_comparison(settings,source.run_id)
    for call in calls:
        assert call['payload']['original_task']['topic']=='Controlled recall mechanisms'
        assert call['payload']['original_task']['boundaries']==['Preserve the user condition.']
        assert call['payload']['original_task']['proposal_details_are_user_constraints'] is False
    arc=[call for call in calls if '.ARC.' in call['task_id']]
    family=next(call for call in arc if call['task']=='NEXT_DRAW')
    for call in arc:
        if call['task']=='COMPOSE' or call['role'] in ('novelty_examiner','selector'):
            assert call['payload']['mandate']==family['payload']['mandate']


@pytest.mark.asyncio
async def test_swapped_orders_reuse_candidates_and_preserve_both_results(tmp_path,monkeypatch):
    settings,store,source,calls=environment(tmp_path,monkeypatch)
    report=await run_comparison(settings,source.run_id,seed=81,include_swapped_order=True)
    assert report['comparison_status']=='completed'
    assert report['shuffle_seed']==81
    assert len(report['evaluations'])==2
    first,second=report['evaluations']
    assert first['identity_map_private']['candidate_1']==second['identity_map_private']['candidate_2']
    assert first['identity_map_private']['candidate_2']==second['identity_map_private']['candidate_1']
    evaluated=[call for call in calls if call['role']=='evaluator']
    assert len(evaluated)==2
    assert evaluated[0]['payload']['candidates'][0]['research_card']==evaluated[1]['payload']['candidates'][1]['research_card']
    assert len([call for call in calls if call['task']=='COMPOSE'])==2
    count=len(calls)
    repeated=await run_comparison(settings,source.run_id,seed=81,include_swapped_order=True)
    assert len(calls)==count and repeated['evaluations']==report['evaluations']
    path=f'evaluations/{source.run_id}/comparison.seed81.both.json'
    original=store.read_artifact(path)
    await run_comparison(settings,source.run_id,seed=82,include_swapped_order=True)
    assert len(calls)==count+2
    assert len([call for call in calls if call['task']=='COMPOSE'])==2
    assert store.read_artifact(path)==original
