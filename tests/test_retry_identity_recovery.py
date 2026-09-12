import json
import pytest
from arc.schemas import TaskRecord
from arc.runtime import RuntimePaused
from tests.test_runtime import setup_runtime, answer, sse, SUBJECT, Result


def prior_task(store):
    store.put_task(TaskRecord(task_id='prior_fixture', run_id=SUBJECT['run_id'],
        status='PAUSED_PROTOCOL', input_hash='fixture', prompt_hash='fixture', model_config_hash='fixture'))


@pytest.mark.asyncio
@pytest.mark.parametrize('handoff', [False, True])
async def test_saved_predecessor_id_slip_resumes_without_another_model_request(tmp_path, handoff):
    raw = answer('unchanged research'); raw['task_id'] = 'prior_fixture'
    runtime, store, ledger, requests = setup_runtime(tmp_path, [sse(json.dumps(raw))])
    prior_task(store)
    payload = ({'evidence_limit_handoff': {'source_task_id':'prior_fixture'}} if handoff
               else {'protocol_retry': {'previous_task_id':'prior_fixture'}})
    original = runtime._normalize_retry_identity
    runtime._normalize_retry_identity = lambda envelope, *args: envelope
    async def invoke():
        return await runtime.invoke('investigator', 'INVOKE', payload, Result, SUBJECT, 'task_fixture')
    with pytest.raises(RuntimePaused, match='SUBJECT_OR_TASK_MISMATCH'):
        await invoke()
    before = store.get_task('task_fixture')
    raw_path = before.response_artifact_path
    saved_before = store.read_artifact(raw_path)
    cost_before = ledger.summary('parent')
    runtime._normalize_retry_identity = original
    accepted = await invoke()
    assert accepted.task_id == 'task_fixture' and accepted.result.value == 'unchanged research'
    assert len(requests) == 1 and ledger.summary('parent') == cost_before
    assert store.read_artifact(raw_path) == saved_before
    saved = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    assert json.loads(saved['response']['message']['content'])['task_id'] == 'prior_fixture'
    assert saved['task_identity_corrections'][0]['from_task_id'] == 'prior_fixture'
    assert store.get_task('task_fixture').error is None
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('wrong_subject,returned_id', [(True,'prior_fixture'), (False,'unrelated_task')])
async def test_subject_change_or_unrelated_id_is_never_normalized(tmp_path, wrong_subject, returned_id):
    raw = answer();raw['task_id']=returned_id
    if wrong_subject:raw['subject']={**SUBJECT,'run_id':'other_run'}
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(json.dumps(raw))]);prior_task(store)
    with pytest.raises(RuntimePaused,match='SUBJECT_OR_TASK_MISMATCH'):
        await runtime.invoke('investigator','INVOKE',{'protocol_retry':{'previous_task_id':'prior_fixture'}},
            Result,SUBJECT,'task_fixture')
    assert store.get_task('task_fixture').accepted_result is None and len(requests)==1
    await runtime.close()
