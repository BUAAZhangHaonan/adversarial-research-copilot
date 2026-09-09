"""Explicit retry of confirmed HTTP 400 preserves UNKNOWN history and old drafts."""
import copy
import json

import pytest

from arc.retrying import prepare_task_retry, retry_working_view
from arc.store import StateError
from tests.test_task_retry import setup_case, failed_task, KEY, REASON


def rejected_case(tmp_path, *, request_error=None, chunks=None, error='BadRequestError'):
    store, ledger, run, card = setup_case(tmp_path)
    task = store.get_task(f'{run.run_id}.{KEY}')
    old = json.loads(store.read_artifact(task.response_artifact_path))
    raw = old['response']['message']['content']
    old['response'].update(call_id='completed-draft', finish_reason='stop')
    response_path = store.save_artifact('tests/completed-draft.json', json.dumps(old))
    ledger.reserve('stage','completed-draft','1',run_id=run.run_id,task_id=task.task_id,
                   model_requested='configured-model')
    ledger.mark_started('completed-draft')
    ledger.settle('completed-draft','1','1','usage_calculated',response_artifact_path=response_path)
    state = copy.deepcopy(old)
    state.update(response=None, pending_model='rejected-call', partial_chunks=[] if chunks is None else chunks,
                 repair_validation_errors=['A known JSON correction was rejected'])
    if request_error is not None:
        state['request_error'] = request_error
    task.response_artifact_path = store.save_artifact('tests/rejected-call.json',json.dumps(state))
    task.status='UNKNOWN'; task.error=error
    store.put_task(task)
    ledger.reserve('stage','rejected-call','2',run_id=run.run_id,task_id=task.task_id,
                   model_requested='configured-model')
    ledger.mark_started('rejected-call')
    ledger.settle('rejected-call','0','2','unknown',error=error)
    store.update_run(run.run_id,status='PAUSED_EXTERNAL',stop_reason='REMOTE_RESULT_UNKNOWN')
    return store,ledger,store.get_run(run.run_id),task,raw


@pytest.mark.parametrize('modern', [False, True])
def test_confirmed_bad_request_creates_new_task_version_without_changing_old_unknown(tmp_path, modern):
    request_error={'type':'BadRequestError','status_code':400} if modern else None
    store,ledger,run,task,raw=rejected_case(tmp_path,request_error=request_error)
    calls=copy.deepcopy(ledger.list_calls())
    task_before=task.model_dump(mode='json')
    artifact=store.read_artifact(task.response_artifact_path)
    retry=prepare_task_retry(store,ledger,run.run_id,KEY,REASON)
    audit=json.loads(store.read_artifact(retry['audit_path']))
    assert retry['replacement_key']==KEY+'.protocol_retry1'
    assert audit['protocol_retry']['unaccepted_response']==raw
    assert audit['recovered_unaccepted_response']['call_id']=='completed-draft'
    assert audit['protocol_retry']['validation_errors']==['A known JSON correction was rejected']
    assert audit['confirmed_rejected_calls'][0]['basis']==('saved_http_status' if modern else 'legacy_sdk_bad_request_type')
    assert ledger.list_calls()==calls
    assert store.get_task(task.task_id).model_dump(mode='json')==task_before
    assert store.read_artifact(task.response_artifact_path)==artifact
    assert store.get_run(run.run_id).status=='RUNNING'
    assert store.get_task(run.run_id+'.'+retry['replacement_key']) is None


@pytest.mark.parametrize('change', ['partial','timeout','wrong_status','wrong_pending','missing_chunks','foreign_run','reserved'])
def test_any_other_unknown_or_inflight_result_blocks_explicit_retry(tmp_path,change):
    store,ledger,run,task,_=rejected_case(tmp_path)
    saved=json.loads(store.read_artifact(task.response_artifact_path))
    if change=='partial':saved['partial_chunks']=[{'partial':'response'}]
    elif change=='wrong_status':saved['request_error']={'type':'BadRequestError','status_code':500}
    elif change=='wrong_pending':saved['pending_model']='another-call'
    elif change=='missing_chunks':saved.pop('partial_chunks')
    elif change=='timeout':task.error='APITimeoutError'
    elif change=='foreign_run':task.run_id='foreign-run'
    elif change=='reserved':ledger.reserve('stage','in-flight','1')
    if change!='foreign_run':
        task.response_artifact_path=store.save_artifact('tests/changed-failure.json',json.dumps(saved));store.put_task(task)
    else:
        # A call attributed to a different run cannot be reclassified by this retry.
        with ledger._connect() as db:
            record=json.loads(db.execute('SELECT metadata FROM budget_calls WHERE call_id=?',('rejected-call',)).fetchone()[0])
            record['run_id']='foreign-run'
            db.execute('UPDATE budget_calls SET metadata=? WHERE call_id=?',(json.dumps(record),'rejected-call'))
    calls=copy.deepcopy(ledger.list_calls())
    with pytest.raises(StateError,match='UNSETTLED'):
        prepare_task_retry(store,ledger,run.run_id,KEY,REASON)
    assert ledger.list_calls()==calls and store.get_run(run.run_id).status=='PAUSED_EXTERNAL'


def test_old_confirmed_rejected_unknown_does_not_block_later_protocol_task_retry(tmp_path):
    store,ledger,run,task,_=rejected_case(tmp_path)
    prepare_task_retry(store,ledger,run.run_id,KEY,REASON)
    other='round2.moderator'
    failed_task(store,run.run_id,other)
    current=store.get_run(run.run_id)
    state=copy.deepcopy(current.state)
    state['task_inputs'][other]=copy.deepcopy(state['task_inputs'][KEY])
    store.update_run(run.run_id,state=state,status='PAUSED_PROTOCOL',stop_reason='INVALID_OUTPUT_AFTER_REPAIR')
    before=copy.deepcopy(ledger.list_calls())
    retry=prepare_task_retry(store,ledger,run.run_id,other,REASON)
    assert retry['replacement_key']==other+'.protocol_retry1'
    assert ledger.list_calls()==before and store.get_task(task.task_id).status=='UNKNOWN'


def test_retry_replaces_old_repeated_id_diagnostics_only_in_working_view(tmp_path):
    store,ledger,run,_=setup_case(tmp_path)
    task=store.get_task(run.run_id+'.'+KEY)
    from arc.schemas import SourceRecord
    known=store.register_source(SourceRecord(title='Actual read paper',url='https://arxiv.org/abs/2107.04034',
        arxiv_id='2107.04034',source_type='paper',access_status='retrieved',content_origin='original'),content='Original material')
    saved=json.loads(store.read_artifact(task.response_artifact_path))
    old_error='OUTPUT_REFERENCE_INVALID; '+json.dumps([{'loc':['result','source_ids',i],
        'type':'unknown_source_id','supplied':'arxiv:2107.04034','visible_candidates':[known.source_id]*500}
        for i in range(22)])
    saved['final_validation_errors']=[old_error]
    saved['tool_trace'][0].update(source_ids=[known.source_id])
    saved['tool_trace'][0]['result'].update(source_id=known.source_id,content='Previously read exact passage')
    task.response_artifact_path=store.save_artifact('tests/old-large-diagnostic.json',json.dumps(saved));store.put_task(task)
    retry=prepare_task_retry(store,ledger,run.run_id,KEY,REASON)
    audit_text=store.read_artifact(retry['audit_path']);audit=json.loads(audit_text)
    assert audit['protocol_retry']['validation_errors']==[old_error]
    view=retry_working_view(audit['protocol_retry'],audit_path=retry['audit_path'])
    assert len(json.dumps(view['validation_errors'])) < len(old_error)/10
    assert 'Actual read paper' in json.dumps(view['validation_errors'])
    assert 'https://arxiv.org/abs/2107.04034' in json.dumps(view['validation_errors'])
    assert view['unaccepted_response']==saved['response']['message']['content']
    assert view['previous_successful_tools']==audit['protocol_retry']['previous_successful_tools']
    assert 'refreshed_validation_errors' not in view
    assert store.read_artifact(retry['audit_path'])==audit_text
