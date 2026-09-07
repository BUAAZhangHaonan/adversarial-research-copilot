"""Offline native-tool protocol correction; no provider or MCP network calls."""
import json
from decimal import Decimal

import pytest

from arc.runtime import BoundTool, Runtime, RuntimePaused
from tests.test_runtime import answer, invoke, setup_runtime, sse


PARAMETERS = {
    'type': 'object',
    'properties': {
        'record_id': {'type': 'string'},
        'offset': {'type': 'integer', 'minimum': 0},
        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 24000},
    },
    'required': ['record_id', 'offset', 'limit'],
    'additionalProperties': False,
}
INVALID = {'record_id': 'source_original', 'offset': 68000, 'limit': 52265}
CORRECTED = {**INVALID, 'limit': 24000}


def native(call_id, arguments, *, index=0, name='read_record'):
    return {'index': index, 'id': call_id, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(arguments)}}


def tool_response(*calls):
    return sse(finish='tool_calls', tools=list(calls))


def native_raw(call_id, arguments_text):
    call = native(call_id, {})
    call['function']['arguments'] = arguments_text
    return call


def fixture(tmp_path, responses, *, amount='20', parameters=PARAMETERS):
    executed = []

    async def read(arguments, metadata):
        executed.append((dict(arguments), dict(metadata)))
        return {'source_ids': [], 'content': 'Synthetic source text.'}

    tool = BoundTool('read_record', parameters, read, Decimal('0'), 'LOCAL')
    runtime, store, ledger, requests = setup_runtime(
        tmp_path, responses, amount=amount, tools={'read_record': tool})
    return runtime, store, ledger, requests, executed


def saved(store):
    return json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))


def restart(runtime):
    """New runtime instance reads the durable checkpoint, with the offline client."""
    return Runtime(store=runtime.store, ledger=runtime.ledger,
                   account_id=runtime.account_id, loader=runtime.loader,
                   role_models=runtime.role_models, prices=runtime.prices,
                   client=runtime.client, tools=runtime.tools)


@pytest.mark.asyncio
async def test_corrected_argument_executes_then_normal_tools_can_continue(tmp_path):
    later = {'record_id': 'source_later', 'offset': 0, 'limit': 100}
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)),
        tool_response(native('corrected_call', CORRECTED)),
        tool_response(native('later_call', later)),
        sse(json.dumps(answer())),
    ])
    assert (await invoke(runtime, tool_profile=['read_record'])).result.value == 'valid'
    assert [args for args, _ in executed] == [CORRECTED, later]
    feedback = [m for m in requests[1]['messages'] if m['role'] == 'tool']
    assert len(feedback) == 1 and feedback[0]['tool_call_id'] == 'bad_original'
    rejected = json.loads(feedback[0]['content'])
    assert rejected['status'] == 'rejected_before_execution'
    assert any(e['path'] == ['limit'] and e['validator'] == 'maximum'
               and e['expected'] == 24000 for e in rejected['errors'])
    originals = [m for m in requests[1]['messages'] if m.get('tool_calls')]
    assert json.loads(originals[0]['tool_calls'][0]['function']['arguments']) == INVALID
    state = saved(store)
    assert state['repair_count'] == 1 and state['repair_kind'] == 'tool_arguments'
    assert state['tool_correction']['phase'] == 'completed'
    assert len(state['tool_rejections']) == 1
    assert len(ledger.list_calls()) == 6  # Four model requests and two executed tools.
    assert all(t['tool_call_id'] != 'bad_original' for t in runtime.tool_trace('task_fixture'))
    before = ledger.summary('parent')
    assert (await invoke(restart(runtime), tool_profile=['read_record'])).result.value == 'valid'
    assert len(requests) == 4 and len(executed) == 2 and ledger.summary('parent') == before
    await runtime.close()


@pytest.mark.asyncio
async def test_second_invalid_argument_stops_without_execution_or_third_request(tmp_path):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)),
        tool_response(native('bad_again', {**INVALID, 'limit': 30000})),
    ])
    with pytest.raises(RuntimePaused, match='TOOL_ARGUMENTS_INVALID_AFTER_CORRECTION'):
        await invoke(runtime, tool_profile=['read_record'])
    assert len(requests) == len(ledger.list_calls()) == 2 and not executed
    assert store.get_task('task_fixture').accepted_result is None
    assert saved(store)['repair_count'] == 1
    await runtime.close()


@pytest.mark.asyncio
async def test_mixed_unknown_limit_and_required_errors_are_corrected_together(tmp_path):
    invalid = {'record_id': INVALID['record_id'], 'limit': INVALID['limit'],
               'undeclared': 'remove this field'}
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', invalid)),
        tool_response(native('corrected_call', CORRECTED)),
        sse(json.dumps(answer())),
    ])
    assert (await invoke(runtime, tool_profile=['read_record'])).result.value == 'valid'
    feedback = [m for m in requests[1]['messages'] if m['role'] == 'tool']
    errors = json.loads(feedback[0]['content'])['errors']
    assert {'additionalProperties', 'maximum', 'required'} <= {e['validator'] for e in errors}
    assert any(e['path'] == ['limit'] and e['expected'] == 24000 for e in errors)
    assert [args for args, _ in executed] == [CORRECTED]
    assert len(requests) == 3 and len(ledger.list_calls()) == 4
    assert saved(store)['repair_count'] == 1
    assert len(saved(store)['tool_rejections']) == 1
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('replacement', [
    {**CORRECTED, 'record_id': 'another_source'},
    {**CORRECTED, 'offset': 0},
])
async def test_correction_cannot_change_other_valid_fields(tmp_path, replacement):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)),
        tool_response(native('changed_target', replacement)),
    ])
    with pytest.raises(RuntimePaused, match='TOOL_CORRECTION_TARGET_CHANGED'):
        await invoke(runtime, tool_profile=['read_record'])
    assert not executed and len(requests) == len(ledger.list_calls()) == 2
    assert store.get_task('task_fixture').accepted_result is None
    await runtime.close()


@pytest.mark.asyncio
async def test_correction_cannot_bundle_an_extra_new_target(tmp_path):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)),
        tool_response(native('corrected_call', CORRECTED), native(
            'extra_call', {**CORRECTED, 'record_id': 'another_source'}, index=1)),
    ])
    with pytest.raises(RuntimePaused):
        await invoke(runtime, tool_profile=['read_record'])
    assert not executed and len(requests) == len(ledger.list_calls()) == 2
    assert store.get_task('task_fixture').accepted_result is None
    await runtime.close()


@pytest.mark.asyncio
async def test_nested_invalid_field_does_not_open_valid_nested_target_to_changes(tmp_path):
    parameters = {'type': 'object', 'properties': {'request': PARAMETERS},
                  'required': ['request'], 'additionalProperties': False}
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', {'request': INVALID})),
        tool_response(native('changed_target', {'request': {**CORRECTED, 'record_id': 'another_source'}})),
        sse(json.dumps(answer())),
    ], parameters=parameters)
    with pytest.raises(RuntimePaused, match='TOOL_CORRECTION_TARGET_CHANGED'):
        await invoke(runtime, tool_profile=['read_record'])
    assert not executed and len(requests) == len(ledger.list_calls()) == 2
    await runtime.close()


@pytest.mark.asyncio
async def test_correction_cannot_add_unrelated_valid_optional_parameter(tmp_path):
    parameters = {**PARAMETERS, 'properties': {**PARAMETERS['properties'],
                  'format': {'type': 'string'}}}
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)),
        tool_response(native('changed_options', {**CORRECTED, 'format': 'new_mode'})),
        sse(json.dumps(answer())),
    ], parameters=parameters)
    with pytest.raises(RuntimePaused, match='TOOL_CORRECTION_TARGET_CHANGED'):
        await invoke(runtime, tool_profile=['read_record'])
    assert not executed and len(requests) == len(ledger.list_calls()) == 2
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('nested', [False, True])
async def test_required_missing_field_or_nested_limit_can_be_corrected(tmp_path, nested):
    if nested:
        parameters = {'type': 'object', 'properties': {'request': PARAMETERS},
                      'required': ['request'], 'additionalProperties': False}
        invalid, corrected = {'request': INVALID}, {'request': CORRECTED}
    else:
        parameters = PARAMETERS
        invalid = {key: value for key, value in CORRECTED.items() if key != 'limit'}
        corrected = CORRECTED
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', invalid)),
        tool_response(native('corrected_call', corrected)), sse(json.dumps(answer())),
    ], parameters=parameters)
    assert (await invoke(runtime, tool_profile=['read_record'])).result.value == 'valid'
    assert [args for args, _ in executed] == [corrected]
    assert len(requests) == 3 and len(ledger.list_calls()) == 4
    await runtime.close()


@pytest.mark.asyncio
async def test_budget_pause_before_correction_resumes_without_replaying_original(tmp_path):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)),
        tool_response(native('corrected_call', CORRECTED)),
        sse(json.dumps(answer())),
    ], amount='5.304')
    with pytest.raises(RuntimePaused) as caught:
        await invoke(runtime, tool_profile=['read_record'])
    assert caught.value.status == 'PAUSED_BUDGET'
    assert len(requests) == 1 and not executed
    assert saved(store)['repair_count'] == 1
    assert saved(store)['tool_correction']['phase'] == 'awaiting'
    assert Decimal(ledger.summary('parent')['reserved_cny']) == 0
    ledger.add_budget('stage', '1', 'Synthetic test authorizes correction continuation')
    resumed = restart(runtime)
    assert (await invoke(resumed, tool_profile=['read_record'])).result.value == 'valid'
    assert len(requests) == 3 and [args for args, _ in executed] == [CORRECTED]
    assert len(saved(store)['tool_rejections']) == 1
    assert len(ledger.list_calls()) == 4
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('crash_point', ['after_sibling', 'before_corrected'])
async def test_completed_sibling_and_saved_correction_survive_restart(tmp_path, crash_point):
    sibling = {'record_id': 'sibling_source', 'offset': 0, 'limit': 20}
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('sibling_call', sibling), native('bad_original', INVALID, index=1)),
        tool_response(native('corrected_call', CORRECTED)),
        sse(json.dumps(answer())),
    ])
    original = runtime._execute_tool

    async def interrupt(record, state, call, profile, parent_call_id):
        if crash_point == 'before_corrected' and call['id'] == 'corrected_call':
            raise SystemExit('synthetic process interruption before corrected tool')
        result = await original(record, state, call, profile, parent_call_id)
        if crash_point == 'after_sibling' and call['id'] == 'sibling_call':
            raise SystemExit('synthetic process interruption after durable sibling')
        return result

    runtime._execute_tool = interrupt
    with pytest.raises(SystemExit):
        await invoke(runtime, tool_profile=['read_record'])
    assert [args for args, _ in executed] == [sibling]
    assert len(requests) == (1 if crash_point == 'after_sibling' else 2)
    resumed = restart(runtime)
    assert (await invoke(resumed, tool_profile=['read_record'])).result.value == 'valid'
    assert [args for args, _ in executed] == [sibling, CORRECTED]
    assert len(requests) == 3 and len(ledger.list_calls()) == 5
    assert len(saved(store)['tool_rejections']) == 1
    tool_messages = [m for m in requests[-1]['messages'] if m['role'] == 'tool']
    assert [m['tool_call_id'] for m in tool_messages].count('sibling_call') == 1
    await runtime.close()


@pytest.mark.asyncio
async def test_tool_correction_consumes_the_json_repair_allowance(tmp_path):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)),
        tool_response(native('corrected_call', CORRECTED)),
        sse('{broken'),
    ])
    with pytest.raises(RuntimePaused, match='INVALID_OUTPUT_AFTER_REPAIR'):
        await invoke(runtime, tool_profile=['read_record'])
    assert len(requests) == 3 and len(executed) == 1 and saved(store)['repair_count'] == 1
    await runtime.close()


@pytest.mark.asyncio
async def test_json_repair_does_not_grant_a_second_tool_correction(tmp_path):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        sse('{broken'), tool_response(native('bad_original', INVALID)),
    ])
    with pytest.raises(RuntimePaused):
        await invoke(runtime, tool_profile=['read_record'])
    assert len(requests) == len(ledger.list_calls()) == 2 and not executed
    assert saved(store)['repair_count'] == 1
    assert saved(store)['repair_kind'] == 'output_json'
    assert not saved(store).get('tool_correction')
    assert store.get_task('task_fixture').accepted_result is None
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('arguments_text', ['["not", "an", "object"]', '{"record_id":'])
async def test_unparseable_original_target_cannot_be_replaced(tmp_path, arguments_text):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native_raw('bad_original', arguments_text)),
        tool_response(native('replacement_call', CORRECTED)),
    ])
    with pytest.raises(RuntimePaused, match='TOOL_CORRECTION_TARGET_UNVERIFIABLE'):
        await invoke(runtime, tool_profile=['read_record'])
    assert not executed and len(requests) == len(ledger.list_calls()) == 2
    assert not runtime.tool_trace('task_fixture')
    assert store.get_task('task_fixture').accepted_result is None
    assert saved(store)['tool_rejections'][0]['original_arguments'] == arguments_text
    await runtime.close()


@pytest.mark.asyncio
async def test_complete_envelope_cannot_skip_required_correction(tmp_path):
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native('bad_original', INVALID)), sse(json.dumps(answer())),
    ])
    with pytest.raises(RuntimePaused, match='TOOL_CORRECTION_REQUIRED'):
        await invoke(runtime, tool_profile=['read_record'])
    assert not executed and len(requests) == 2 and store.get_task('task_fixture').accepted_result is None
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('arguments_text', [json.dumps(INVALID), '["not", "an", "object"]', '{"record_id":'])
async def test_blocked_capability_request_can_decline_without_running_overlimit_tool(tmp_path, arguments_text):
    blocked = answer()
    blocked.update(result_status='blocked', result=None, note='Requested range exceeds the available tool limit.',
                   capability_requests=[{
                       'blocked_question': 'Can the complete source passage be read atomically?',
                       'needed_operation': 'read a larger passage', 'input_fields': ['record_id', 'offset', 'limit'],
                       'required_output': 'source passage', 'provenance_needs': 'source identity and coverage',
                       'cost_visibility_needs': 'local read cost', 'acceptance_example': 'a verified passage',
                       'current_limitation': 'read_record limit is at most 24000',
                       'proposed_change': 'Evaluate a larger bounded local read limit',
                       'rationale': 'The requested passage is longer than one tool response.',
                       'alternatives': ['Read multiple ranges within the current limit.'],
                       'expected_impact': 'More source context per response; more model input tokens.',
                   }])
    runtime, store, ledger, requests, executed = fixture(tmp_path, [
        tool_response(native_raw('bad_original', arguments_text)), sse(json.dumps(blocked)),
    ])
    result = await invoke(runtime, tool_profile=['read_record'])
    assert result.result_status == 'blocked' and len(result.capability_requests) == 1
    assert not executed and len(requests) == len(ledger.list_calls()) == 2
    assert saved(store)['tool_correction']['phase'] == 'declined'
    assert store.get_task('task_fixture').status == 'PAUSED_EXTERNAL'
    assert json.loads(saved(store)['response']['message']['content'])['result_status'] == 'blocked'
    await runtime.close()
