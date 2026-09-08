"""Archive addressing uses the existing JSON repair allowance."""
from copy import deepcopy
import json
import pytest
from arc.runtime import RuntimePaused
from arc.schemas import LibrarianResult
from arc.validation import validate_archive_comparisons
from tests.test_runtime import SUBJECT, answer, setup_runtime, sse
from tests.test_archive_comparisons import cards, records, result_for, invalid_result


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'unknown'])
async def test_runtime_archive_contract_uses_existing_json_correction_before_acceptance(tmp_path, kind):
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses)
    runtime.role_models['librarian'] = 'deepseek-v4-pro'
    first, extra = cards(store)
    valid = result_for(first, extra)
    for result in [invalid_result(valid, kind), valid]:
        envelope = answer()
        envelope['result'] = result.model_dump(mode='json')
        responses.append(sse(json.dumps(envelope), model='deepseek-v4-pro'))
    payload = {'records_to_compare': records(first)}
    try:
        accepted = await runtime.invoke('librarian', 'INVOKE', payload, LibrarianResult,
            SUBJECT, 'task_fixture', tool_profile=[])
        assert accepted.result == valid
        assert len(requests) == len(ledger.list_calls()) == 2
        assert 'comparisons' in requests[1]['messages'][1]['content']
        assert store.get_task('task_fixture').status == 'ACCEPTED'
        # Accepted additional records are replayed, never deleted or rewritten.
        frozen = deepcopy(store.get_task('task_fixture'))
        again = await runtime.invoke('librarian', 'INVOKE', payload, LibrarianResult,
            SUBJECT, 'task_fixture', tool_profile=[])
        validate_archive_comparisons(again.result, records(first), store)
        assert len(requests) == 2 and store.get_task('task_fixture') == frozen
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_archive_contract_has_no_extra_allowance_after_json_repair(tmp_path):
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses)
    runtime.role_models['librarian'] = 'deepseek-v4-pro'
    first, extra = cards(store)
    envelope = answer()
    envelope['result'] = result_for(extra).model_dump(mode='json')
    responses.extend([sse('{broken', model='deepseek-v4-pro'), sse(json.dumps(envelope), model='deepseek-v4-pro')])
    try:
        with pytest.raises(RuntimePaused, match='INVALID_OUTPUT_AFTER_REPAIR'):
            await runtime.invoke('librarian', 'INVOKE', {'records_to_compare': records(first)},
                LibrarianResult, SUBJECT, 'task_fixture', tool_profile=[])
        assert len(requests) == 2
        assert store.get_task('task_fixture').accepted_result is None
        state = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        assert 'ARCHIVE_COMPARISON_COVERAGE' in str(state['final_validation_errors'])
        assert first.card_id in str(state['final_validation_errors'])
    finally:
        await runtime.close()
