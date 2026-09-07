import json
from decimal import Decimal

import pytest

from arc.runtime import BoundTool, RuntimePaused, derive_investigator_searches
from arc.schemas import Envelope, InvestigatorResult
from .test_runtime import SUBJECT, answer, setup_runtime, sse
from .test_store import source


def research_answer():
    body = answer()
    body['result'] = {
        'questions_addressed': ['What was observed?'],
        'actual_searches': [{'trace_id': 'model_echo', 'operation': 'search_web',
                            'query': 'controlled observation', 'source_ids': ['fixture_sourc']}],
        'findings': [{'claim': 'A controlled observation.', 'conditions': ['synthetic'],
                      'source_id': 'fixture_source', 'locator': 'L2',
                      'locator_status': 'verified', 'relation': 'motivates', 'origin': 'original',
                      'excerpt': 'A controlled observation.',
                      'support_explanation': 'The passage supplies a background observation.'}],
        'contrary_findings': [], 'source_access_limits': [],
        'implications_for_current_card': [], 'unresolved_questions': [],
        'recommended_next_action': 'REASON'}
    return body


def tool_response():
    return sse(finish='tool_calls', tools=[{'index': 0, 'id': 'provider_search',
        'type': 'function', 'function': {'name': 'search_web',
        'arguments': '{"query":"controlled observation"}'}}])


def fixture_runtime(tmp_path, responses):
    async def search(arguments, metadata):
        return {'source_ids': ['fixture_source']}
    tool = BoundTool('search_web', {'type': 'object', 'properties': {
        'query': {'type': 'string'}}, 'required': ['query']}, search, Decimal(0), 'LOCAL')
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses, tools={'search_web': tool})
    source(store)
    return runtime, store, ledger, requests


async def invoke_research(runtime, payload=None, profile=None):
    return await runtime.invoke('investigator', 'INVOKE', payload or {'question': 'Observe'},
        InvestigatorResult, SUBJECT, 'task_fixture', tool_profile=['search_web'] if profile is None else profile)


@pytest.mark.asyncio
async def test_saved_repaired_metadata_recovers_without_additional_sdk_request(tmp_path):
    raw = research_answer()
    runtime, store, ledger, requests = fixture_runtime(tmp_path, [tool_response(), sse('not JSON'), sse(json.dumps(raw))])
    normalize = runtime._normalize_search_provenance
    runtime._normalize_search_provenance = lambda envelope, record, state: envelope
    with pytest.raises(RuntimePaused, match='unknown_source_id'):
        await invoke_research(runtime)
    paused = store.get_task('task_fixture')
    old_path = paused.response_artifact_path
    old_state_bytes = store.read_artifact(old_path)
    assert json.loads(old_state_bytes)['repair_count'] == 1
    assert paused.accepted_result is None
    cost, calls = ledger.summary('parent'), len(ledger.list_calls())
    runtime._normalize_search_provenance = normalize
    result = await invoke_research(runtime)
    assert len(requests) == 3 and len(ledger.list_calls()) == calls
    assert ledger.summary('parent') == cost and store.read_artifact(old_path) == old_state_bytes
    accepted = store.get_task('task_fixture')
    assert accepted.status == 'ACCEPTED' and accepted.error is None
    state = json.loads(store.read_artifact(accepted.response_artifact_path))
    assert state['repair_count'] == 1
    assert json.loads(state['response']['message']['content']) == raw
    audit = json.loads(store.read_artifact(state['actual_searches_provenance']['audit_path']))
    assert audit['prior_task_status'] == 'PAUSED_PROTOCOL' and audit['prior_error'] == 'unknown_source_id'
    assert audit['original_model_declaration'] == raw['result']['actual_searches']
    assert audit['research_fields_before_hash'] == audit['research_fields_after_hash']
    trace = runtime.tool_trace('task_fixture')[0]
    assert result.result.actual_searches[0].model_dump() == {
        'trace_id': trace['call_id'], 'operation': 'search_web',
        'query': 'controlled observation', 'source_ids': ['fixture_source']}
    assert result.result.findings[0].excerpt == raw['result']['findings'][0]['excerpt']
    assert await invoke_research(runtime) == result
    assert len(requests) == 3 and ledger.summary('parent') == cost
    assert store.get_task('task_fixture') == accepted
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value,error', [
    ('source_id', 'unknown_scientific_source', 'unknown_source_id'),
    ('excerpt', 'A rewritten observation absent from the original.', 'excerpt_not_in_returned_source')])
async def test_mechanical_logs_do_not_repair_scientific_findings(tmp_path, field, value, error):
    raw = research_answer()
    raw['result']['findings'][0][field] = value
    runtime, store, ledger, requests = fixture_runtime(tmp_path, [tool_response(), sse(json.dumps(raw))])
    with pytest.raises(RuntimePaused, match=error):
        await invoke_research(runtime)
    task = store.get_task('task_fixture')
    assert task.accepted_result is None
    state = json.loads(store.read_artifact(task.response_artifact_path))
    assert json.loads(state['response']['message']['content']) == raw
    assert state['repair_count'] == 0
    with pytest.raises(RuntimePaused, match=error):
        await invoke_research(runtime)
    assert len(requests) == 2
    await runtime.close()


@pytest.mark.asyncio
async def test_cached_historical_acceptance_returns_audited_view_without_rewriting_record(tmp_path):
    raw = research_answer()
    runtime, store, ledger, requests = fixture_runtime(tmp_path, [tool_response(), sse(json.dumps(raw))])
    normalize = runtime._normalize_search_provenance
    runtime._normalize_search_provenance = lambda envelope, record, state: envelope
    with pytest.raises(RuntimePaused, match='unknown_source_id'):
        await invoke_research(runtime)
    # Seed the historical acceptance under the old policy, without modifying its raw response.
    legacy = store.get_task('task_fixture')
    legacy.accepted_result = Envelope[InvestigatorResult].model_validate(raw).model_dump(mode='json')
    legacy.status = 'ACCEPTED'
    store.put_task(legacy)
    before = store.get_task('task_fixture').model_dump(mode='json')
    old_bytes = store.read_artifact(legacy.response_artifact_path)
    cost = ledger.summary('parent')
    paths = []
    save = store.save_artifact
    def capture(path, content):
        paths.append(path)
        return save(path, content)
    store.save_artifact = capture
    runtime._normalize_search_provenance = normalize
    result = await invoke_research(runtime)
    assert result.result.actual_searches[0].source_ids == ['fixture_source']
    assert store.get_task('task_fixture').model_dump(mode='json') == before
    assert store.read_artifact(legacy.response_artifact_path) == old_bytes
    assert len(paths) == 1 and '/normalizations/' in paths[0]
    audit = json.loads(store.read_artifact(paths[0]))
    assert audit['original_model_declaration'] == raw['result']['actual_searches']
    assert audit['prior_task_status'] == 'ACCEPTED'
    assert await invoke_research(runtime) == result
    assert len(paths) == 1 and len(requests) == 2 and ledger.summary('parent') == cost
    assert store.get_task('task_fixture').model_dump(mode='json') == before
    await runtime.close()


def trace(**updates):
    value = {'task_id': 'task_fixture', 'run_id': SUBJECT['run_id'], 'call_id': 'real_search',
             'name': 'search_web', 'status': 'completed',
             'arguments': {'query': 'controlled observation'}, 'source_ids': ['fixture_source']}
    value.update(updates)
    return value


def test_derivation_uses_only_current_completed_searches_and_never_mutates_input():
    envelope = Envelope[InvestigatorResult].model_validate(research_answer())
    original = envelope.model_dump(mode='json')
    traces = [trace(), trace(call_id='failed', status='error'),
              trace(call_id='read', name='read_record'), trace(call_id='pending', status='pending')]
    result = derive_investigator_searches(envelope, traces)
    assert len(result.result.actual_searches) == 1
    assert envelope.model_dump(mode='json') == original
    assert result.result.findings == envelope.result.findings
    with pytest.raises(ValueError, match='SEARCH_TRACE_TASK_MISMATCH'):
        derive_investigator_searches(envelope, [trace(task_id='parent_task')])
    with pytest.raises(ValueError, match='SEARCH_TRACE_TASK_MISMATCH'):
        derive_investigator_searches(envelope, [trace(run_id='parent_run')])
    with pytest.raises(ValueError, match='DUPLICATE_SEARCH_TRACE_ID'):
        derive_investigator_searches(envelope, [trace(), trace()])


@pytest.mark.asyncio
async def test_audit_written_before_acceptance_checkpoint_crash_recovers_idempotently(tmp_path):
    runtime, store, ledger, requests = fixture_runtime(tmp_path,
        [tool_response(), sse(json.dumps(research_answer()))])
    checkpoint = runtime._checkpoint
    audit_paths = []
    save = store.save_artifact
    def capture(path, content):
        if '/normalizations/' in path:
            audit_paths.append(path)
        return save(path, content)
    store.save_artifact = capture
    def crash_before_acceptance(record, state, status=None):
        if status == 'ACCEPTED':
            assert len(audit_paths) == 1
            raise OSError('fixture crash after audit before acceptance checkpoint')
        return checkpoint(record, state, status)
    runtime._checkpoint = crash_before_acceptance
    with pytest.raises(OSError, match='fixture crash after audit'):
        await invoke_research(runtime)
    prior = store.get_task('task_fixture')
    assert prior.accepted_result is None
    old_bytes = store.read_artifact(prior.response_artifact_path)
    assert 'actual_searches_provenance' not in json.loads(old_bytes)
    audit_bytes = store.read_artifact(audit_paths[0])
    cost, calls = ledger.summary('parent'), len(ledger.list_calls())
    runtime._checkpoint = checkpoint
    result = await invoke_research(runtime)
    assert result.result.actual_searches[0].source_ids == ['fixture_source']
    assert len(audit_paths) == 1 and store.read_artifact(audit_paths[0]) == audit_bytes
    assert store.read_artifact(prior.response_artifact_path) == old_bytes
    accepted = store.get_task('task_fixture')
    state = json.loads(store.read_artifact(accepted.response_artifact_path))
    assert state['actual_searches_provenance']['audit_path'] == audit_paths[0]
    assert accepted.status == 'ACCEPTED' and accepted.error is None
    assert len(requests) == 2 and len(ledger.list_calls()) == calls
    assert ledger.summary('parent') == cost
    await runtime.close()


@pytest.mark.asyncio
async def test_parent_payload_search_history_cannot_become_current_tool_execution(tmp_path):
    raw = research_answer()
    runtime, store, ledger, requests = fixture_runtime(tmp_path, [sse(json.dumps(raw))])
    result = await invoke_research(runtime, payload={
        'source_ids': ['fixture_source'], 'prior_investigation': raw['result'],
        'parent_tool_trace': [trace(task_id='parent_task')]}, profile=[])
    assert result.result.actual_searches == []
    assert result.result.findings[0].source_id == 'fixture_source'
    assert len(requests) == 1 and runtime.tool_trace('task_fixture') == []
    await runtime.close()
