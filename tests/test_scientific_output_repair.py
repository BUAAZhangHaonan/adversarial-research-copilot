"""Existing runtime JSON allowance covers scientific addressing, not new research."""
from copy import deepcopy
import json
import pytest

from arc.runtime import RuntimePaused
from arc.schemas import Claim,ScientificReview
from tests.test_runtime import setup_runtime,sse,answer,SUBJECT
from tests.test_selection import research_draft
from tests.test_scientific_cycle import review,defect,resolution


def setup_review(tmp_path):
    responses=[]
    runtime,store,ledger,requests=setup_runtime(tmp_path,responses)
    runtime.role_models['scientific_reviewer']='deepseek-v4-pro'
    draft=research_draft()
    draft.motivation.evidence_ids=[]
    draft.closest_work_delta.source_ids=[]
    draft.claims=[Claim(claim_id='claim_logic',version=1,text='The two conditions share one measurement.',
        conditions=['a fixed synthetic task'],kind='logical',evidence_ids=[])]
    original=store.save_card(draft,run_id=SUBJECT['run_id'])
    proposed=draft.model_copy(deep=True)
    proposed.claims[0].text='The two fixed conditions use the same measurement.'
    payload={'review_target':proposed.model_dump(mode='json'),
        'original_card':original.model_dump(mode='json'),'proposed_revision':proposed.model_dump(mode='json'),
        'previous_review':None}
    subject={**SUBJECT,'card_id':original.card_id,'card_version':original.version}
    valid=review(edits=[{'claim_id':'claim_logic','change_kind':'unchanged_meaning',
                        'reason':'Only restates the same measurement-sharing assumption.'}]).model_dump(mode='json')
    return runtime,store,ledger,requests,responses,payload,subject,valid


def encoded_result(result,subject):
    envelope=answer()
    envelope.update(task_id='task_fixture',subject=subject,result=result)
    return sse(json.dumps(envelope),model='deepseek-v4-pro')


async def invoke_review(runtime,payload,subject):
    return await runtime.invoke('scientific_reviewer','INVOKE',payload,ScientificReview,subject,'task_fixture',tool_profile=[])


@pytest.mark.asyncio
async def test_missing_claim_classification_uses_one_existing_json_repair_without_changing_science(tmp_path):
    runtime,store,ledger,requests,responses,payload,subject,valid=setup_review(tmp_path)
    malformed=deepcopy(valid);malformed['edit_assessments']=[]
    responses.extend([encoded_result(malformed,subject),encoded_result(valid,subject)])
    try:
        result=await invoke_review(runtime,payload,subject)
        assert result.result.model_dump(mode='json')==valid
        assert len(requests)==2 and len(ledger.list_calls())==2
        assert requests[0]['messages'][0]==requests[1]['messages'][0]
        feedback=requests[1]['messages'][1]['content']
        assert 'CLAIM_EDIT_REVIEW_COVERAGE' in feedback and 'claim_logic' in feedback
        state=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        assert state['repair_count']==1
        before=deepcopy(malformed);after=result.result.model_dump(mode='json')
        before.pop('edit_assessments');after.pop('edit_assessments')
        assert before==after
        count=len(requests)
        await invoke_review(runtime,payload,subject)
        assert len(requests)==count
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_prior_finding_coverage_uses_same_repair_without_changing_review(tmp_path):
    runtime,store,ledger,requests,responses,payload,subject,valid=setup_review(tmp_path)
    previous=review('revise',findings=[defect()]).model_dump(mode='json')
    payload['previous_review']=previous
    valid['prior_findings']=[resolution('reviewer_error')]
    malformed=deepcopy(valid);malformed['prior_findings']=[]
    responses.extend([encoded_result(malformed,subject),encoded_result(valid,subject)])
    try:
        result=await invoke_review(runtime,payload,subject)
        assert len(requests)==2 and result.result.prior_findings[0].status=='reviewer_error'
        assert 'SCIENTIFIC_RECHECK_MUST_ADDRESS_PREVIOUS_FINDINGS' in requests[1]['messages'][1]['content']
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_correct_scientific_output_gets_no_extra_call(tmp_path):
    runtime,store,ledger,requests,responses,payload,subject,valid=setup_review(tmp_path)
    responses.append(encoded_result(valid,subject))
    try:
        result=await invoke_review(runtime,payload,subject)
        assert result.result.model_dump(mode='json')==valid and len(requests)==1
        state=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        assert state['repair_count']==0
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_structure_then_missing_classification_does_not_get_second_json_allowance(tmp_path):
    runtime,store,ledger,requests,responses,payload,subject,valid=setup_review(tmp_path)
    malformed=deepcopy(valid);malformed['edit_assessments']=[]
    responses.extend([sse('{broken',model='deepseek-v4-pro'),encoded_result(malformed,subject)])
    try:
        with pytest.raises(RuntimePaused,match='INVALID_OUTPUT_AFTER_REPAIR'):
            await invoke_review(runtime,payload,subject)
        assert len(requests)==2 and len(ledger.list_calls())==2
        record=store.get_task('task_fixture')
        assert record.status=='PAUSED_PROTOCOL' and record.accepted_result is None
        state=json.loads(store.read_artifact(record.response_artifact_path))
        assert state['repair_count']==1
        assert 'CLAIM_EDIT_REVIEW_COVERAGE' in str(state['final_validation_errors'])
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_inconsistent_retain_is_diagnosed_and_action_corrected_without_value_inflation(tmp_path):
    runtime,store,ledger,requests,responses,payload,subject,valid=setup_review(tmp_path)
    malformed=deepcopy(valid);malformed['value_judgment']='routine'
    corrected=deepcopy(malformed);corrected['action']='reject'
    responses.extend([encoded_result(malformed,subject),encoded_result(corrected,subject)])
    try:
        result=await invoke_review(runtime,payload,subject)
        assert result.result.value_judgment=='routine' and result.result.action=='reject'
        assert result.result.decisive_findings==[]
        assert len(requests)==2
        feedback=requests[1]['messages'][1]['content']
        assert 'value_judgment=routine' in feedback and 'value_judgment=substantial' in feedback
        assert result.result.value_reason==valid['value_reason']
    finally:
        await runtime.close()
