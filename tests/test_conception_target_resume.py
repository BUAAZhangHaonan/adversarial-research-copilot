"""A legacy post-response target pause can resume its paid result locally."""
import json

import pytest

from arc.runtime import RuntimePaused, correction_counts
from arc.schemas import Claim, ConceptionResult
from arc.store import StateError
from tests.test_runtime import SUBJECT, request_answer, setup_runtime, sse
from tests.test_selection import research_draft


@pytest.mark.asyncio
async def test_conception_declared_claim_resumes_cached_response_without_another_model_call(tmp_path, monkeypatch):
    draft = research_draft()
    draft.motivation.evidence_ids = []
    draft.closest_work_delta.source_ids = []
    draft.claims = [Claim(claim_id='claim_new', version=1, text='A proposed testable effect.',
        conditions=['controlled task'], kind='hypothesis', evidence_ids=[])]
    raw = request_answer(claim_id='claim_new')
    raw['result'] = {'card_candidate': draft.model_dump(mode='json'), 'continue_or_stop': 'CONTINUE',
        'composition_reason': 'The question merits testing.', 'distinct_from_retained': 'First candidate.'}
    runtime, store, ledger, requests = setup_runtime(tmp_path, [sse(json.dumps(raw), model='deepseek-v4-pro')])
    runtime.role_models['discovery'] = 'deepseek-v4-pro'
    validate = runtime._validate_semantics

    def old_omission(envelope, payload, state):
        validate(envelope, payload, state)
        raise StateError('evidence_request_claim_id_not_supplied_to_task')

    monkeypatch.setattr(runtime, '_validate_semantics', old_omission)
    try:
        with pytest.raises(RuntimePaused, match='evidence_request_claim_id_not_supplied_to_task'):
            await runtime.invoke('discovery', 'CONCEIVE', {}, ConceptionResult, SUBJECT, 'task_fixture', tool_profile=[])
        paused = store.get_task('task_fixture')
        original_artifact = store.read_artifact(paused.response_artifact_path)
        assert paused.status == 'PAUSED_PROTOCOL' and paused.accepted_result is None
        assert correction_counts(json.loads(original_artifact))['output_json'] == 0
        assert len(requests) == len(ledger.list_calls()) == 1
        monkeypatch.setattr(runtime, '_validate_semantics', validate)
        accepted = await runtime.invoke('discovery', 'CONCEIVE', {}, ConceptionResult,
            SUBJECT, 'task_fixture', tool_profile=[])
        assert accepted.model_dump(mode='json') == raw
        assert store.get_task('task_fixture').status == 'ACCEPTED'
        assert len(requests) == len(ledger.list_calls()) == 1
        assert store.read_artifact(paused.response_artifact_path) == original_artifact
    finally:
        await runtime.close()
