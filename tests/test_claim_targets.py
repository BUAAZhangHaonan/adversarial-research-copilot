"""Claim omission and frozen role-target boundaries, without model calls."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from arc.schemas import CardDraft, DeveloperResult, Envelope, ProposerResult, SkepticResult
from arc.store import Store
from arc.validation import ProtocolViolation, validate_revision, validate_role_targets
from .test_contracts import card_payload


def claim(identifier='current_c1', version=2):
    return {'claim_id':identifier, 'version':version, 'text':'A bounded hypothesis.',
            'conditions':['fixed setting'], 'kind':'hypothesis', 'evidence_ids':[]}


def revision_payload(original, revised):
    return {'proposed_revision':revised, 'direction_change':None,
        'unchanged_problem_anchor':original['problem_anchor'], 'change_summary':['Explicit withdrawal.'],
        'affected_claims':[c['claim_id'] for c in original['claims']],
        'evidence_review':[{'claim_id':c['claim_id'], 'claim_version':c['version'],
            'evidence_ids':[], 'still_applicable':True,
            'explanation':'The observation remains valid, but this claim is withdrawn.'} for c in original['claims']],
        'minimal_test':None, 'resources':None, 'remaining_issues':[], 'next_action':'STOP'}


def test_omitted_revision_claims_are_not_silently_converted_to_withdrawal():
    original=card_payload(); original['claims']=[claim('draft_c1',1),claim('draft_c2',1)]
    omitted=deepcopy(original); del omitted['claims']
    raw=revision_payload(original,omitted)
    raw['change_summary']=['Claim text and versions are unchanged.']
    with pytest.raises(ValidationError) as caught:
        DeveloperResult.model_validate(raw)
    assert any(error['loc']==('proposed_revision','claims') and error['type']=='missing'
               for error in caught.value.errors())
    assert 'claims' in CardDraft.model_json_schema()['required']
    assert CardDraft.model_validate(card_payload()).claims==[]


@pytest.mark.parametrize('invalid_review',[{'claim_version':1},{'explanation':''},{'explanation':'  \n '}])
def test_deleted_claim_review_requires_old_version_and_real_explanation(tmp_path,invalid_review):
    store=Store(tmp_path/'claims.sqlite')
    original=card_payload(); original['claims']=[claim(version=2)]
    card=store.save_card(original)
    raw=revision_payload(original,card_payload())
    raw['evidence_review'][0].update(invalid_review)
    with pytest.raises(ProtocolViolation,match='DELETED_CLAIM_REVIEW_VERSION_OR_EXPLANATION'):
        validate_revision(store,card,DeveloperResult.model_validate(raw))
    assert store.get_card(card.card_id).version==1


def test_explicit_claim_withdrawal_preserves_original_and_allows_empty_revision(tmp_path):
    store=Store(tmp_path/'claims.sqlite')
    original=card_payload(); original['claims']=[claim(version=2)]
    card=store.save_card(original)
    revision=DeveloperResult.model_validate(revision_payload(original,card_payload()))
    validate_revision(store,card,revision)
    revised=store.save_card(revision.proposed_revision,card_id=card.card_id,parent_version=1)
    assert revised.draft.claims==[]
    assert store.get_card(card.card_id,1).draft.claims[0].version==2


def role_payload(*,empty_claims=False):
    draft=card_payload(); draft['claims']=[] if empty_claims else [claim()]
    return {'card':{'card_id':'card1','version':2,'draft':draft},'issues':[],
        'evidence':[{'claim_id':'old_c1','claim_version':1}],
        'original_card':{'card_id':'card1','version':1,'draft':{'claims':[claim('old_c1',1)]}}}


def envelope(result):
    return Envelope[type(result)](schema_version='arc.v1',task_id='run1.role',
        subject={'campaign_id':None,'run_id':'run1','card_id':'card1','card_version':2},
        result_status='complete',result=result,evidence_requests=[],capability_requests=[],note=None)


def skeptic(*,claim_id='current_c1',issue_id=None):
    return SkepticResult(criticisms=[{'issue_id':issue_id,'local_label':'new-objection' if issue_id is None else None,
        'severity':'material','claim_id':claim_id,'claim':'A scientific claim.',
        'rationale':'A counterexample matters.','impact':'Changes the interpretation.',
        'evidence_ids':[],'resolution_criterion':'An explicit discriminating observation.'}],
        resolved_objections=[],surviving_decisive_issues=[],required_evidence_or_test=[],suggested_next_action='REASON')


def proposer(issue_id=None):
    return ProposerResult(claims_defended=['A supported explanation, not an identifier.'],
        claims_narrowed=['Limit the claim to the observed setting.'],
        claims_withdrawn=['Withdraw the stronger interpretation.'],proposed_method_changes=[],
        issue_responses=[] if issue_id is None else [{'issue_id':issue_id,'response':'Explicit argument.',
            'evidence_ids':[],'proposed_change':'Narrow the claim.'}],
        new_argument_or_evidence=[],suggested_next_action='REASON')


@pytest.mark.parametrize('target',['old_c1','unknown_c1'])
def test_skeptic_cannot_create_current_issue_from_background_or_old_card_claim(target):
    with pytest.raises(ProtocolViolation,match='SKEPTIC_CLAIM_NOT_IN_CURRENT_CARD'):
        validate_role_targets(envelope(skeptic(claim_id=target)),role_payload())


def test_real_shape_empty_current_claims_and_no_issues_rejects_old_criticism():
    payload=role_payload(empty_claims=True)
    with pytest.raises(ProtocolViolation,match='SKEPTIC_CLAIM_NOT_IN_CURRENT_CARD'):
        validate_role_targets(envelope(skeptic(claim_id='old_c1')),payload)


def test_skeptic_current_claim_and_explicit_existing_historical_issue_are_valid():
    validate_role_targets(envelope(skeptic()),role_payload())
    payload=role_payload(empty_claims=True)
    payload['issues']=[{'issue_id':'historic-I1','claim_id':'old_c1','claim_version':1}]
    validate_role_targets(envelope(skeptic(claim_id='old_c1',issue_id='historic-I1')),payload)
    # The ledger does not permit creating a new current-card issue for that old ID.
    with pytest.raises(ProtocolViolation,match='SKEPTIC_CLAIM_NOT_IN_CURRENT_CARD'):
        validate_role_targets(envelope(skeptic(claim_id='old_c1')),payload)


def test_skeptic_existing_issue_must_belong_to_ledger_and_match_its_claim():
    payload=role_payload(); payload['issues']=[{'issue_id':'I1','claim_id':'old_c1','claim_version':1}]
    with pytest.raises(ProtocolViolation,match='SKEPTIC_ISSUE_NOT_IN_CURRENT_LEDGER'):
        validate_role_targets(envelope(skeptic(issue_id='foreign-I1')),payload)
    with pytest.raises(ProtocolViolation,match='SKEPTIC_ISSUE_CLAIM_MISMATCH'):
        validate_role_targets(envelope(skeptic(issue_id='I1')),payload)


def test_proposer_only_explicit_issue_ids_are_checked_not_claim_prose():
    validate_role_targets(envelope(proposer()),role_payload(empty_claims=True))
    payload=role_payload(); payload['issues']=[{'issue_id':'I1','claim_id':'old_c1','claim_version':1}]
    validate_role_targets(envelope(proposer('I1')),payload)
    payload['evidence'].append({'issue_id':'foreign-I1'})
    with pytest.raises(ProtocolViolation,match='PROPOSER_ISSUE_NOT_IN_CURRENT_LEDGER'):
        validate_role_targets(envelope(proposer('foreign-I1')),payload)


def test_role_target_card_is_the_enclosing_subject_and_ledger_ids_are_unambiguous():
    payload=role_payload(); payload['card']['version']=1
    with pytest.raises(ProtocolViolation,match='ROLE_TARGET_CARD_SUBJECT_MISMATCH'):
        validate_role_targets(envelope(skeptic()),payload)
    payload=role_payload(); payload['issues']=[{'issue_id':'I1','claim_id':'a'},{'issue_id':'I1','claim_id':'b'}]
    with pytest.raises(ProtocolViolation,match='ROLE_TARGET_DUPLICATE_ISSUE_ID'):
        validate_role_targets(envelope(proposer()),payload)


@pytest.mark.asyncio
async def test_runtime_rejects_background_claim_target_preserves_raw_and_resumes_without_call(tmp_path):
    from arc.runtime import RuntimePaused
    from .test_runtime import setup_runtime, sse, answer, SUBJECT
    from .test_store import source, evidence
    responses=[]
    runtime,store,ledger,requests=setup_runtime(tmp_path,responses)
    runtime.role_models['skeptic']='deepseek-v4-flash'
    card=store.save_card(card_payload())
    store.update_run(SUBJECT['run_id'],card_id=card.card_id,card_version=card.version)
    observation=evidence(store,source(store),claim_id='old_c1')
    subject={**SUBJECT,'card_id':card.card_id,'card_version':card.version}
    payload={'card':card.model_dump(mode='json'),'issues':[],
        'evidence':[observation.model_dump(mode='json')]}
    raw=answer();raw['subject']=subject;raw['result']=skeptic(claim_id='old_c1').model_dump(mode='json')
    raw_text=json.dumps(raw)
    responses.append(sse(raw_text))
    async def call():
        return await runtime.invoke('skeptic','INVOKE',payload,SkepticResult,subject,'task_fixture',tool_profile=[])
    try:
        with pytest.raises(RuntimePaused,match='SKEPTIC_CLAIM_NOT_IN_CURRENT_CARD'):
            await call()
        task=store.get_task('task_fixture')
        assert task.status=='PAUSED_PROTOCOL' and task.accepted_result is None
        state=json.loads(store.read_artifact(task.response_artifact_path))
        assert state['response']['message']['content']==raw_text and state['repair_count']==0
        cost=ledger.summary('parent')
        assert len(requests)==1 and len(ledger.list_calls())==1
        with pytest.raises(RuntimePaused,match='SKEPTIC_CLAIM_NOT_IN_CURRENT_CARD'):
            await call()
        assert len(requests)==1 and ledger.summary('parent')==cost
        assert store.get_task('task_fixture').accepted_result is None
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_runtime_missing_revision_claims_repairs_once_before_workflow_saves_card(tmp_path):
    from arc.config import Settings
    from arc.workflows import WorkflowEngine
    from .test_runtime import setup_runtime, sse, answer, SUBJECT
    responses=[]
    runtime,store,ledger,requests=setup_runtime(tmp_path,responses)
    runtime.role_models['developer']='deepseek-v4-flash'
    original=card_payload();original['claims']=[claim('draft_c1',1),claim('draft_c2',1)]
    card=store.save_card(original)
    store.update_run(SUBJECT['run_id'],card_id=card.card_id,card_version=card.version)
    subject={**SUBJECT,'card_id':card.card_id,'card_version':card.version}
    omitted=deepcopy(original);del omitted['claims']
    raw=answer();raw['task_id']=SUBJECT['run_id']+'.development';raw['subject']=subject
    raw['result']=revision_payload(original,omitted)
    raw['result']['change_summary']=['Claim text and versions are unchanged.']
    repaired=deepcopy(raw);repaired['result']['proposed_revision']=deepcopy(original)
    repaired['result']['affected_claims']=[];repaired['result']['evidence_review']=[]
    responses.extend([sse(json.dumps(raw)),sse(json.dumps(repaired))])
    engine=WorkflowEngine(store,runtime,Settings())
    # Isolate the developer boundary while retaining the real workflow call,
    # runtime/SDK, revision validator and immutable card persistence.
    async def existing_investigation(run_id,*args,**kwargs):
        engine.checkpoint(run_id,fresh_verification={})
    observed=[]
    async def observe_next_stage(run_id):
        run=store.get_run(run_id)
        observed.append(store.get_card(run.card_id,run.card_version))
    engine.investigate=existing_investigation
    engine.debate=observe_next_stage
    try:
        await engine.develop(SUBJECT['run_id'])
        assert len(requests)==2 and len(ledger.list_calls())==2
        task=store.get_task(raw['task_id'])
        assert task.status=='ACCEPTED'
        state=json.loads(store.read_artifact(task.response_artifact_path))
        assert state['repair_count']==1
        assert 'Repair an invalid structured response' in requests[1]['messages'][1]['content']
        assert any(error['loc']==['result','proposed_revision','claims'] for error in state['repair_validation_errors'])
        assert observed[0].version==2
        assert [c.model_dump() for c in observed[0].draft.claims]==original['claims']
        for version in (1,2):
            assert store.get_card(card.card_id,version).draft.claims
        cost=ledger.summary('parent')
        await engine.develop(SUBJECT['run_id'])
        assert len(requests)==2 and ledger.summary('parent')==cost
        assert store.get_card(card.card_id).version==2
    finally:
        await runtime.close()
