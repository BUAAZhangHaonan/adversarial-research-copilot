"""Real-store interrupted evidence reselection, without paid services."""
from copy import deepcopy
from collections import Counter
import pytest

from arc.schemas import Claim,Finding,InvestigatorResult,TaskRecord
from arc.scientific import review_and_revise
from arc.validation import ProtocolViolation
from tests.test_selection import research_store,research_draft
from tests.test_scientific_cycle import CheckpointEngine,review


def setup_support(tmp_path):
    store,source,evidence=research_store(tmp_path)
    campaign=store.create_campaign('Separate distance and interference',['equal model budget'])
    run=store.create_run('develop',campaign_id=campaign.campaign_id)
    draft=research_draft()
    draft.claims=[Claim(claim_id=evidence.claim_id,version=1,text=evidence.claim,
        conditions=evidence.conditions,kind='empirical',evidence_ids=[evidence.evidence_id])]
    original=store.save_card(draft,run_id=run.run_id)
    proposed=draft.model_copy(deep=True)
    proposed.claims[0].text='The reported recall decrease covaries with distance and distractors in this synthetic task.'
    result=review(edits=[{'claim_id':evidence.claim_id,'change_kind':'substantive',
                         'reason':'The revised proposition changes the scope of the empirical statement.'}])
    return store,store.get_run(run.run_id),original,proposed,result


class SupportEngine(CheckpointEngine):
    def __init__(self,*args,source_recheck=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.source_recheck=source_recheck

    def trace_tasks(self,run_id,key):
        return self.store.get_run(run_id).state.get(key+'_trace_tasks',[run_id+'.'+key])

    async def investigate(self,run_id,key,questions,*,fresh=False,extra=None):
        current=self.store.get_card(self.store.get_run(run_id).card_id,self.store.get_run(run_id).card_version)
        claim=current.draft.claims[0]
        text=self.store.get_record('src_synthetic')['content']
        excerpt='Moving relevant facts farther away lowered recall. Distractor count also changed.'
        finding=Finding.model_validate({'claim':claim.text,'conditions':claim.conditions,
            'claim_id':claim.claim_id,'claim_version':claim.version,'source_id':'src_synthetic',
            'locator':f'chars:{text.index(excerpt)}:{text.index(excerpt)+len(excerpt)}','locator_status':'verified',
            'relation':'limits','origin':'original','excerpt':excerpt,
            'support_explanation':'The passage supports only the reported joint change, not a causal explanation.'})
        result=InvestigatorResult.model_validate({'questions_addressed':['Reassess current claim support'],
            'actual_searches':[],'findings':[finding.model_dump(mode='json')],'contrary_findings':[],
            'source_access_limits':[],'implications_for_current_card':['Keep the causal interpretation hypothetical.'],
            'unresolved_questions':[],'recommended_next_action':'STOP'})
        physical=key+'.source_recheck' if self.source_recheck else key
        self.outputs[physical]=result
        result=await self.call(run_id,physical,'investigator',payload={**self.context(run_id),**(extra or {})})
        records=self.store.register_findings(result.findings,task_id=run_id+'.'+physical,allowed_claims=current.draft.claims)
        self.checkpoint(run_id,**{key+'_trace_tasks':[run_id+'.'+physical]},
            evidence_ids=[record.evidence_id for record in records])
        return result


@pytest.mark.asyncio
async def test_support_uses_already_registered_physical_source_recheck_task(tmp_path,monkeypatch):
    store,run,original,proposed,initial=setup_support(tmp_path)
    engine=SupportEngine(store,{'science.review':initial,'science.support_review':review()},source_recheck=True)
    registrations=[]
    real=store.register_findings
    def tracked(findings,task_id,**kwargs):
        registrations.append(task_id)
        return real(findings,task_id,**kwargs)
    monkeypatch.setattr(store,'register_findings',tracked)
    card,result=await review_and_revise(engine,run.run_id,'science',original=original,proposed=proposed)
    assert result.action=='retain' and card.version==3
    assert registrations==[run.run_id+'.science.support_recheck.source_recheck']
    assert len(store.list_evidence())==2
    current=store.list_evidence(ids=card.draft.claims[0].evidence_ids)
    assert len(current)==1 and current[0].claim_version==2
    assert current[0].evidence_id!='ev_synthetic'
    assert store.get_record('ev_synthetic')['claim_version']==1


@pytest.mark.asyncio
async def test_support_pause_restores_original_target_and_current_subject_without_replay(tmp_path):
    store,run,original,proposed,initial=setup_support(tmp_path)
    engine=SupportEngine(store,{'science.review':initial,'science.support_review':review()},
        interrupt_before='science.support_review')
    with pytest.raises(InterruptedError):
        await review_and_revise(engine,run.run_id,'science',original=original,proposed=proposed)
    assert store.get_run(run.run_id).card_version==2
    # A discovery caller restores its draw's initial cursor before resuming.
    store.update_run(run.run_id,card_version=1)
    card,result=await review_and_revise(engine,run.run_id,'science')
    assert card.version==3 and result.action=='retain'
    assert engine.invocations==['science.review','science.support_recheck','science.support_review']
    frozen=store.get_run(run.run_id).state['task_inputs']['science.support_review']
    assert frozen['subject']['card_version']==2
    assert frozen['payload']['card']['version']==2
    assert frozen['payload']['original_card']['version']==2
    assert frozen['payload']['review_target']['claims'][0]['version']==2
    assert len(store.list_evidence())==2
    assert store.get_run(run.run_id).card_version==3


@pytest.mark.asyncio
async def test_resume_rejects_changed_explicit_proposal_before_any_new_call(tmp_path):
    store,run,original,proposed,initial=setup_support(tmp_path)
    engine=SupportEngine(store,{'science.review':initial,'science.support_review':review()},
        interrupt_before='science.support_review')
    with pytest.raises(InterruptedError):
        await review_and_revise(engine,run.run_id,'science',original=original,proposed=proposed)
    changed=proposed.model_copy(deep=True)
    changed.title='A silently changed proposal'
    count=len(engine.invocations)
    with pytest.raises(ProtocolViolation,match='SCIENTIFIC_PROPOSED_INPUT_CHANGED'):
        await review_and_revise(engine,run.run_id,'science',original=original,proposed=changed)
    assert len(engine.invocations)==count


@pytest.mark.asyncio
async def test_post_support_card_commit_crash_recovers_without_new_cards_or_calls(tmp_path,monkeypatch):
    store,run,original,proposed,initial=setup_support(tmp_path)
    engine=SupportEngine(store,{'science.review':initial,'science.support_review':review()})
    real=store.save_card
    crashed=False
    def after_commit(*args,**kwargs):
        nonlocal crashed
        card=real(*args,**kwargs)
        if str(kwargs.get('creation_key','')).endswith('.support.card') and not crashed:
            crashed=True
            raise InterruptedError('Synthetic process exit after support card committed')
        return card
    monkeypatch.setattr(store,'save_card',after_commit)
    with pytest.raises(InterruptedError):
        await review_and_revise(engine,run.run_id,'science',original=original,proposed=proposed)
    count=len(engine.invocations)
    card,result=await review_and_revise(engine,run.run_id,'science')
    assert card.version==3 and len(store.list_cards(run_id=run.run_id))==3
    assert len(engine.invocations)==count and store.get_run(run.run_id).card_version==3
