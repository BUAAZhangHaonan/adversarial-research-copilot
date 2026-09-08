import copy
import json

import pytest

from arc.config import Settings
from arc.retrying import prepare_task_retry, retry_working_view
from arc.workflows import WorkflowEngine
from tests.test_task_retry import KEY, REASON, setup_case
from tests.test_workflows import ScriptedRuntime


def read(result, source='source_a', **extra):
    return {'name': 'read_record', 'status': 'completed',
        'arguments': {'record_id': source}, 'result': result, **extra}


def test_only_empty_source_boundary_reads_are_condensed_without_mutating_input():
    empty = read({'content': '', 'requires_source_fetch': True,
        'cached_content_chars': 22000, 'content_total_chars': 38026})
    kept = [
        read({'content': 'real original', 'requires_source_fetch': True}),
        read({'content': None, 'cached_content_chars': 0, 'requires_source_fetch': True}),
        read({'source_type': 'paper', 'access_status': 'metadata_only'}),
        read({'content': '', 'content_origin': 'metadata', 'requires_source_fetch': True}),
        read({'content': '', 'access_status': 'metadata_only', 'requires_source_fetch': True}),
        read({'content': ''}),
        read({'requires_source_fetch': True}),
        {'name': 'read_record', 'result': {'content': '', 'requires_source_fetch': True}},
        {'name': 'search_web', 'result': {'content': '', 'requires_source_fetch': True}},
    ]
    original = {'previous_successful_tools': [empty, *kept, copy.deepcopy(empty),
        read({'content': '', 'error': 'SOURCE_END_REACHED', 'cached_content_chars': 30,
              'content_complete': True}, source='source_b')], 'validation_errors': [{'type': 'old'}]}
    before = copy.deepcopy(original)
    view = retry_working_view(original, audit_path='immutable/retry.json')
    assert original == before
    assert view['previous_successful_tools'] == kept
    summaries = view['previous_source_read_boundaries']
    assert len(summaries) == 2
    assert summaries[0]['source_id'] == 'source_a' and summaries[0]['omitted_empty_reads'] == 2
    assert summaries[0]['cached_content_chars'] == 22000
    assert summaries[1]['error'] == 'SOURCE_END_REACHED'
    assert view['previous_successful_tools_audit_path'] == 'immutable/retry.json'
    view['validation_errors'][0]['type'] = 'changed working copy'
    assert original == before


def test_absent_history_fields_are_safe():
    original = {'previous_task_id': 'old'}
    assert retry_working_view(original) == {**original, 'previous_successful_tools': []}
    assert original == {'previous_task_id': 'old'}


@pytest.mark.asyncio
async def test_new_retry_task_freezes_condensed_view_and_preserves_raw_audit(tmp_path):
    store, ledger, run, card = setup_case(tmp_path)
    task = store.get_task(f'{run.run_id}.{KEY}')
    saved = json.loads(store.read_artifact(task.response_artifact_path))
    saved['tool_trace'].extend([read({'content': '', 'requires_source_fetch': True,
        'cached_content_chars': 20, 'content_total_chars': 30}) for _ in range(3)])
    task.response_artifact_path = store.save_artifact('tests/with-empty-reads.json', json.dumps(saved))
    store.put_task(task)
    original_trace = store.read_artifact(task.response_artifact_path)
    retry = prepare_task_retry(store, ledger, run.run_id, KEY, REASON)
    audit_text = store.read_artifact(retry['audit_path'])
    assert len(json.loads(audit_text)['protocol_retry']['previous_successful_tools']) == 4
    runtime = ScriptedRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    await engine.call(run.run_id, KEY, 'moderator')
    payload = runtime.calls[0]['payload']['protocol_retry']
    assert len(payload['previous_successful_tools']) == 1
    assert payload['previous_source_read_boundaries'][0]['omitted_empty_reads'] == 3
    assert store.get_run(run.run_id).state['task_inputs'][retry['replacement_key']]['payload']['protocol_retry'] == payload
    assert store.read_artifact(retry['audit_path']) == audit_text
    assert store.read_artifact(task.response_artifact_path) == original_trace
