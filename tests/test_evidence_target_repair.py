"""Only request addressing joins JSON correction; research content stays intact."""
from copy import deepcopy
import json

import pytest

from arc.runtime import RuntimePaused, correction_counts
from tests.test_runtime import Result, SUBJECT, request_answer, setup_runtime, sse


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['claim_id', 'issue_id', 'draw_id'])
async def test_unknown_request_target_gets_one_json_correction_with_expected_and_supplied(tmp_path, field):
    malformed = request_answer(**{field: 'unknown_target'})
    corrected = deepcopy(malformed)
    corrected['evidence_requests'][0][field] = 'current_target'
    runtime, store, ledger, requests = setup_runtime(tmp_path,
        [sse(json.dumps(malformed)), sse(json.dumps(corrected))])
    payload = {field + 's': ['current_target']}
    try:
        result = await runtime.invoke('investigator', 'INVOKE', payload, Result,
            SUBJECT, 'task_fixture', tool_profile=[])
        assert result.model_dump(mode='json') == corrected
        assert len(requests) == len(ledger.list_calls()) == 2
        feedback = requests[1]['messages'][1]['content']
        assert 'expected' in feedback and 'current_target' in feedback
        assert 'supplied' in feedback and 'unknown_target' in feedback
        assert 'evidence_requests' in feedback and field in feedback
        record = store.get_task('task_fixture')
        assert record.status == 'ACCEPTED'
        assert correction_counts(json.loads(store.read_artifact(record.response_artifact_path))) == {
            'tool_arguments': 0, 'output_json': 1}
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_target_error_does_not_refresh_an_already_spent_json_allowance(tmp_path):
    malformed = request_answer(claim_id='unknown_target')
    runtime, store, ledger, requests = setup_runtime(tmp_path,
        [sse('{broken'), sse(json.dumps(malformed))])
    try:
        with pytest.raises(RuntimePaused, match='INVALID_OUTPUT_AFTER_REPAIR'):
            await runtime.invoke('investigator', 'INVOKE', {'claim_ids': ['current_target']}, Result,
                SUBJECT, 'task_fixture', tool_profile=[])
        assert len(requests) == len(ledger.list_calls()) == 2
        record = store.get_task('task_fixture')
        assert record.accepted_result is None
        errors = json.loads(store.read_artifact(record.response_artifact_path))['final_validation_errors']
        assert 'evidence_request_claim_id_not_supplied_to_task' in str(errors)
        assert 'current_target' in str(errors) and 'unknown_target' in str(errors)
    finally:
        await runtime.close()
