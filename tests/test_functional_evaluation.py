"""Ablation comparability and paid-call reuse, checked entirely with local replies."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from arc.budget import BudgetLedger
from arc.config import Settings
from arc.functional_evaluation import run_ablation
from arc.schemas import Envelope, TaskRecord
from arc.validation import ProtocolViolation
from tests.test_selection import research_store, research_draft, selection_result, novelty_result
from tests.test_scientific_cycle import defect, review, patch, resolution


class LocalRuntime:
    def __init__(self, store, calls, run, phase, settings, *, fail_key=None):
        self.store, self.calls, self.run = store, calls, run
        self.phase, self.settings, self.fail_key = phase, settings, fail_key

    async def close(self):
        pass

    async def invoke(self, *, role, task, payload, result_schema, subject, task_id, tool_profile):
        assert tool_profile == []
        self.calls.append({'task_id': task_id, 'role': role, 'task': task,
            'phase': self.phase, 'model': self.settings.roles[role], 'payload': deepcopy(payload)})
        if self.fail_key and self.fail_key in task_id:
            raise ProtocolViolation('SYNTHETIC_CONDITION_FAILURE')
        if task == 'CONCEIVE':
            result = dict(card_candidate=research_draft().model_dump(mode='json'),
                continue_or_stop='CONTINUE', composition_reason='Different remedies require separating interventions.',
                distinct_from_retained='First candidate.')
        elif task == 'FRAME':
            result = dict(mandate=dict(topic=payload['topic'], research_object='Controlled recall',
                scope_in=['Both interventions'], scope_out=['Pretraining'], known_constraints=[],
                unknown_constraints=[]), initial_search_questions=[])
        elif task == 'NEXT_DRAW':
            result = dict(continue_or_stop='CONTINUE', proposed_family='Separate the interventions',
                anchor_evidence_ids=['ev_synthetic'], distinct_from_retained='First direction.',
                relevant_archive_relations=[], missing_information=[], why_this_draw_is_worthwhile='Different remedies.')
        elif task == 'COMPOSE':
            result = dict(card_candidate=research_draft().model_dump(mode='json'),
                          composition_reason='A controlled intervention.', unresolved_prerequisites=[])
        elif task == 'REVISE':
            result = patch(research_draft()).model_dump(mode='json')
        elif role == 'novelty_examiner':
            result = novelty_result().model_dump(mode='json')
        elif role == 'selector':
            result = selection_result().model_dump(mode='json')
        elif role == 'scientific_reviewer':
            result = (review('retain', resolutions=[resolution()]) if task_id.endswith('.recheck') else
                      review('revise', findings=[defect()])).model_dump(mode='json')
        elif role == 'evaluator':
            result = dict(per_candidate_findings=[dict(candidate_id=c['candidate_id'],
                findings=['Synthetic comparison only.'], evidence_ids=[]) for c in payload['candidates']],
                decisive_errors=[], supported_strengths=[], unresolved_verifications=[],
                preference_if_requested=None, uncertainty='No research-quality inference from this fixture.')
        else:
            raise AssertionError((role, task))
        envelope = Envelope[result_schema](schema_version='arc.v1', task_id=task_id, subject=subject,
            result_status='complete', result=result_schema.model_validate(result), evidence_requests=[],
            capability_requests=[], note=None)
        response = self.store.save_artifact(f'tests/{task_id}.json', envelope.model_dump_json())
        prompt = self.store.save_artifact(f'tests/{task_id}.prompt.json', json.dumps({'prompt_id': f'{role}.{task}'}))
        self.store.put_task(TaskRecord(task_id=task_id, run_id=subject.run_id, input_hash='fixture',
            prompt_hash='fixture', model_config_hash='fixture', status='ACCEPTED',
            rendered_prompt_path=prompt, response_artifact_path=response,
            accepted_result=envelope.model_dump(mode='json')))
        return envelope


def environment(tmp_path, monkeypatch, *, fail_key=None):
    import arc.cli
    store, _, evidence = research_store(tmp_path)
    ledger = BudgetLedger(store.db_path)
    ledger.create_account('authorized-parent', '100')
    settings = Settings(data_dir=tmp_path)
    campaign = store.create_campaign('Separate distance and interference.', ['Equal budget', 'Keep both interventions'])
    source = store.create_run('discover', campaign_id=campaign.campaign_id,
        state={'evidence_ids': [evidence.evidence_id]})
    monkeypatch.setattr(arc.cli, 'services', lambda _: (store, ledger))
    calls = []
    async def factory(run, phase, config):
        return LocalRuntime(store, calls, run, phase, config, fail_key=fail_key)
    arguments = dict(experiment_id='ablation-test', parent_id='authorized-parent', budget_cny='20',
        seed=9, legacy_prompt_root=Path(__file__).parent / 'fixtures/prompts_pre_redesign', runtime_factory=factory)
    return settings, store, ledger, source, calls, arguments


@pytest.mark.asyncio
async def test_ablation_controls_models_prompts_materials_and_reuses_candidate_and_initial_review(tmp_path, monkeypatch):
    settings, store, ledger, source, calls, arguments = environment(tmp_path, monkeypatch)
    report = await run_ablation(settings, source.run_id, **arguments)
    assert report['status'] == 'completed'
    assert list(report['conditions']) == list('ABCDE')
    assert all(item['status'] == 'COMPLETED' for item in report['conditions'].values())
    assert report['conditions']['A']['draft'] == report['conditions']['D']['draft']
    assert report['conditions']['E']['draft']['minimal_test'] != report['conditions']['A']['draft']['minimal_test']
    assert report['conditions']['D']['judgment']['action'] == 'revise'
    assert report['conditions']['E']['judgment']['action'] == 'retain'
    assert not any(item['task_id'] == 'ablation-test.E.science.review' for item in calls)
    assert len([item for item in calls if item['task'] == 'CONCEIVE']) == 1
    e = store.get_run('ablation-test.E')
    assert e.state['reused_reviews']['science.review']['source_task_id'] == 'ablation-test.D.science.review'
    for item in calls:
        condition = item['task_id'].split('.')[1]
        assert item['payload']['original_task']['topic'] == 'Separate distance and interference.'
        if condition in 'BC' and item['role'] == 'discovery':
            assert item['model'] == ('deepseek-v4-flash' if condition == 'C' else 'deepseek-v4-pro')
        else:
            assert item['model'] == 'deepseek-v4-pro'
        if item['role'] in {'novelty_examiner', 'selector'}:
            assert condition in 'ABC' and item['phase'] == 'legacy'
        else:
            assert item['phase'] == 'current'
    manifest = json.loads(store.read_artifact(report['material_path']))
    assert all('current generation prompts' in manifest['conditions'][condition] for condition in 'ABC')
    assert store.get_campaign(source.campaign_id).draws_started == 0
    assert ledger.summary('authorized-parent')['limit_cny'] == '100.000000'
    assert len(report['evaluations']) == 2
    first, second = report['evaluations']
    assert [v['system'] for v in first['identity_map_private'].values()] == \
        list(reversed([v['system'] for v in second['identity_map_private'].values()]))
    for item in calls:
        if item['role'] == 'evaluator':
            assert all(set(c) == {'candidate_id', 'research_card'} for c in item['payload']['candidates'])


@pytest.mark.asyncio
async def test_ablation_resume_reuses_all_completed_steps_and_rejects_changed_seed(tmp_path, monkeypatch):
    settings, store, _, source, calls, arguments = environment(tmp_path, monkeypatch)
    first = await run_ablation(settings, source.run_id, **arguments)
    paid_before = deepcopy(calls)
    second = await run_ablation(settings, source.run_id, **arguments)
    # _frozen_call may create a Runtime but never invokes it for a saved envelope.
    assert calls == paid_before
    assert first == second
    with pytest.raises(ProtocolViolation, match='INPUT_CHANGED'):
        await run_ablation(settings, source.run_id, **{**arguments, 'seed': 10})


@pytest.mark.asyncio
async def test_ablation_preserves_failed_arm_and_other_results_without_judging_incomplete_set(tmp_path, monkeypatch):
    settings, store, _, source, calls, arguments = environment(tmp_path, monkeypatch, fail_key='.B.compose')
    report = await run_ablation(settings, source.run_id, **arguments)
    assert report['status'] == 'incomplete'
    assert report['conditions']['B']['status'] == 'PAUSED_PROTOCOL'
    assert report['conditions']['B']['stop_reason'] == 'SYNTHETIC_CONDITION_FAILURE'
    assert report['conditions']['A']['draft'] is not None
    assert report['conditions']['C']['draft'] is not None
    assert report['conditions']['E']['judgment']['action'] == 'retain'
    assert not any(c['role'] == 'evaluator' for c in calls)
    artifact = json.loads(store.read_artifact('functional-evaluations/ablation-test/report.json'))
    assert artifact['conditions']['B']['status'] == 'PAUSED_PROTOCOL'


@pytest.mark.asyncio
async def test_unsettled_paid_request_stops_before_starting_another_condition(tmp_path, monkeypatch):
    settings, store, ledger, source, calls, arguments = environment(tmp_path, monkeypatch)
    async def factory(run, phase, config):
        runtime = LocalRuntime(store, calls, run, phase, config, fail_key='.A.conception')
        invoke = runtime.invoke
        async def outstanding(**kwargs):
            ledger.reserve(run.budget_account_id, 'unfinished-provider-call', '1')
            ledger.mark_started('unfinished-provider-call')
            return await invoke(**kwargs)
        runtime.invoke = outstanding
        return runtime
    report = await run_ablation(settings, source.run_id, **{**arguments, 'runtime_factory': factory})
    assert report['stop_reason'] == 'parent_has_unsettled_model_call'
    assert report['blocked_remaining_conditions'] == list('BCDE')
    assert list(report['conditions']) == ['A']
    assert len(calls) == 1
    with pytest.raises(ValueError, match='PARENT_HAS_PENDING_CALLS'):
        await run_ablation(settings, source.run_id, **arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize('failed_key,waiting', [('.A.conception', 'DE'), ('.D.science.review', 'E')])
async def test_upstream_recovery_revisits_dependent_arms_without_regenerating_candidates(
        tmp_path, monkeypatch, failed_key, waiting):
    settings, store, _, source, calls, arguments = environment(tmp_path, monkeypatch, fail_key=failed_key)
    first = await run_ablation(settings, source.run_id, **arguments)
    for condition in waiting:
        assert first['conditions'][condition]['status'] == 'PAUSED_EXTERNAL'
        assert not store.get_run('ablation-test.' + condition).state.get('functional_result')
    completed_generation = [c for c in calls if c['task'] in {'CONCEIVE', 'COMPOSE'} and failed_key not in c['task_id']]
    async def recovered(run, phase, config):
        return LocalRuntime(store, calls, run, phase, config)
    second = await run_ablation(settings, source.run_id, **{**arguments, 'runtime_factory': recovered})
    assert second['status'] == 'completed'
    for accepted in completed_generation:
        assert len([c for c in calls if c['task_id'] == accepted['task_id']]) == 1
    assert second['conditions']['D']['draft'] == second['conditions']['A']['draft']
    assert second['conditions']['E']['judgment']['action'] == 'retain'


@pytest.mark.asyncio
async def test_failed_old_review_preserves_a_candidate_for_d_and_e(tmp_path, monkeypatch):
    settings, store, _, source, calls, arguments = environment(tmp_path, monkeypatch, fail_key='.A.novelty')
    first = await run_ablation(settings, source.run_id, **arguments)
    assert first['conditions']['A']['status'] == 'PAUSED_PROTOCOL'
    assert first['conditions']['D']['draft'] == first['conditions']['A']['draft']
    assert first['conditions']['E']['judgment']['action'] == 'retain'
    async def recovered(run, phase, config):
        return LocalRuntime(store, calls, run, phase, config)
    second = await run_ablation(settings, source.run_id, **{**arguments, 'runtime_factory': recovered})
    assert second['status'] == 'completed'
    assert len([c for c in calls if c['task'] == 'CONCEIVE']) == 1
