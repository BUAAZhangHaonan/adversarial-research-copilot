"""Capability proposals are records and handoffs, never execution authority."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from arc.cli import app, services
from arc.config import Settings
from arc.reports import render_capability_handoff
from arc.schemas import CapabilityRequest, CapabilityReview, Envelope, RESULT_SCHEMAS
from arc.store import StateError
from arc.workflows import WorkflowEngine, WorkflowPause


def request_payload():
    return dict(blocked_question='Need to inspect a longer original passage',needed_operation='read_record',
        input_fields=['record_id','offset','limit'],required_output='Cached original text and coverage metadata',
        provenance_needs='Preserve source ID and exact offsets',cost_visibility_needs='No new model call during this review',
        acceptance_example='A 64000 character page is returned without changing the original source',
        current_limitation='Current read_record per-call limit is 16000 characters',
        proposed_change='Evaluate a 64000 character per-call limit',rationale='Fewer page reads may simplify inspection',
        alternatives=['Continue paging within the existing 16000 character limit; more calls but no service change'],
        expected_impact='Potentially fewer reads and larger model context; evaluate memory and token cost before changing it')


def review_payload(assessment='recommended'):
    return dict(assessment=assessment,rationale='Check actual serialized size and paging behavior before adopting the limit',
        recommended_option='Make the documented and enforced limit 64000' if assessment=='recommended' else None,
        implementation_scope=['Change the advertised and enforced read_record limit together'] if assessment=='recommended' else [],
        validation_plan=['Test 64000 accepted, 64001 rejected, original source and budget unchanged'] if assessment=='recommended' else [])


def test_request_is_actionable_and_review_recommendation_requires_validation():
    CapabilityRequest.model_validate(request_payload())
    for name in ('current_limitation','proposed_change','rationale','alternatives','expected_impact'):
        value=request_payload(); del value[name]
        with pytest.raises(ValidationError): CapabilityRequest.model_validate(value)
    value=review_payload(); value['validation_plan']=[]
    with pytest.raises(ValidationError): CapabilityReview.model_validate(value)


def test_durable_requests_review_and_handoff_do_not_grant_authority(tmp_path):
    store,ledger=services(Settings(data_dir=tmp_path))
    run=store.create_run('discover')
    ledger.create_account('account','20')
    before=ledger.summary('account'); original_run=store.get_run(run.run_id)
    identifier=store.save_capability_request(run.run_id,request_payload(),task_id='task-a',request_key='task-a.envelope.0')
    record=store.get_capability_request(identifier)
    assert record['status']=='pending_codex_review' and record['review'] is None
    assert '尚未评估，不生成执行支线' in render_capability_handoff(record)
    assert store.save_capability_request(run.run_id,request_payload(),task_id='task-a',request_key='task-a.envelope.0')==identifier
    reviewed=store.review_capability_request(identifier,review_payload())
    assert reviewed['status']=='reviewed' and reviewed['task_id']=='task-a'
    assert store.review_capability_request(identifier,review_payload())==reviewed
    assert '用户执行支线交付模板' in render_capability_handoff(reviewed)
    assert '没有创建或启动任何任务' in render_capability_handoff(reviewed)
    for key,value in request_payload().items(): assert reviewed[key]==value
    changed=review_payload(); changed['rationale']='Replacement review'
    with pytest.raises(StateError,match='already_recorded'): store.review_capability_request(identifier,changed)
    assert store.get_record(identifier)==reviewed
    assert ledger.summary('account')==before and store.get_run(run.run_id)==original_run
    assert len(store.list_capability_requests(run.run_id))==1


@pytest.mark.parametrize('assessment',['needs_information','not_recommended'])
def test_non_recommendations_have_no_execution_handoff(tmp_path,assessment):
    store,_=services(Settings(data_dir=tmp_path)); run=store.create_run('discover')
    identifier=store.save_capability_request(run.run_id,request_payload())
    record=store.review_capability_request(identifier,review_payload(assessment))
    assert '## 用户执行支线' not in render_capability_handoff(record)


def test_cli_record_review_export_is_entirely_offline(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('No research execution permitted')
    monkeypatch.setattr('arc.cli.execute',forbidden)
    store,ledger=services(Settings(data_dir=tmp_path/'data'))
    run=store.create_run('discover'); ledger.create_account('account','20')
    budget=ledger.summary('account')
    request=tmp_path/'request.json'; request.write_text(json.dumps(request_payload()),encoding='utf-8')
    review=tmp_path/'review.json'; review.write_text(json.dumps(review_payload()),encoding='utf-8')
    runner=CliRunner(); base=['--data-dir',str(tmp_path/'data'),'requirements']
    result=runner.invoke(app,[*base,'add',run.run_id,'--request',str(request)])
    assert result.exit_code==0,result.output
    identifier=result.output.strip()
    result=runner.invoke(app,[*base,'review',identifier,'--review',str(review)])
    assert result.exit_code==0,result.output
    output=tmp_path/'handoff.md'
    result=runner.invoke(app,[*base,'export',identifier,'--output',str(output)])
    assert result.exit_code==0,result.output
    assert '64000' in output.read_text(encoding='utf-8')
    result=runner.invoke(app,[*base,'list',run.run_id])
    assert result.exit_code==0 and json.loads(result.output)[0]['status']=='reviewed'
    assert ledger.summary('account')==budget


@pytest.mark.parametrize('status',['complete','blocked'])
def test_workflow_records_requests_with_task_source_on_all_results(tmp_path,status):
    store,_=services(Settings(data_dir=tmp_path)); run=store.create_run('discover')
    schema=RESULT_SCHEMAS['discovery.FRAME']
    calls=[]
    class Runtime:
        tools={'read_record':object(),'request_capability':object()}
        loader=SimpleNamespace(manifest={'prompts':{'discovery.FRAME':{'tools':['read_record','request_capability']}}})
        async def invoke(self,**kwargs):
            calls.append(kwargs)
            return Envelope[schema](schema_version='arc.v1',task_id=kwargs['task_id'],subject=kwargs['subject'],
                result_status=status,result=schema.model_validate(dict(mandate=dict(topic='topic',research_object='object',scope_in=[],scope_out=[],known_constraints=[],unknown_constraints=[]),initial_search_questions=[])) if status=='complete' else None,
                evidence_requests=[],capability_requests=[CapabilityRequest.model_validate(request_payload())],note=None if status=='complete' else 'A tool improvement is requested')
        def tool_trace(self,task_id): return []
    engine=WorkflowEngine(store,Runtime(),Settings(data_dir=tmp_path))
    for _ in range(2):
        if status=='blocked':
            with pytest.raises(WorkflowPause): asyncio.run(engine.call(run.run_id,'frame','discovery','FRAME',tool_profile=['read_record']))
        else: asyncio.run(engine.call(run.run_id,'frame','discovery','FRAME',tool_profile=['read_record']))
    records=store.list_capability_requests(run.run_id)
    assert len(records)==1 and records[0]['task_id']==run.run_id+'.frame'
    assert calls[0]['tool_profile']==['read_record','request_capability']
