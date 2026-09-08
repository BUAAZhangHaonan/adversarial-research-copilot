"""A submitted candidate continues to review; STOP never carries a card."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from arc.schemas import ConceptionResult
from tests.test_runtime import SUBJECT, answer, setup_runtime, sse
from tests.test_selection import research_draft


@pytest.mark.parametrize('action,has_card', [('CONTINUE', True), ('CONTINUE', False), ('STOP', False)])
def test_valid_conception_action_combinations(action, has_card):
    candidate = research_draft() if has_card else None
    result = ConceptionResult(card_candidate=candidate, continue_or_stop=action,
        composition_reason='A single candidate decision.', distinct_from_retained='First candidate.')
    assert result.card_candidate == candidate and result.continue_or_stop == action


def test_stop_with_candidate_has_actionable_technical_diagnostic():
    with pytest.raises(ValidationError, match='STOP_requires_card_candidate_null; use_CONTINUE_to_submit_candidate'):
        ConceptionResult(card_candidate=research_draft(), continue_or_stop='STOP',
            composition_reason='Do not submit a second candidate.', distinct_from_retained='First candidate.')


@pytest.mark.asyncio
async def test_runtime_existing_json_repair_can_submit_same_candidate_with_continue(tmp_path):
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses)
    runtime.role_models['discovery'] = 'deepseek-v4-pro'
    draft = research_draft()
    draft.motivation.evidence_ids = []
    draft.closest_work_delta.source_ids = []
    malformed = {'card_candidate': draft.model_dump(mode='json'), 'continue_or_stop': 'STOP',
        'composition_reason': 'Do not submit a second candidate.', 'distinct_from_retained': 'First candidate.'}
    corrected = {**deepcopy(malformed), 'continue_or_stop': 'CONTINUE'}
    for result in [malformed, corrected]:
        envelope = answer()
        envelope['result'] = result
        responses.append(sse(json.dumps(envelope), model='deepseek-v4-pro'))
    try:
        result = await runtime.invoke('discovery', 'CONCEIVE', {}, ConceptionResult,
            SUBJECT, 'task_fixture', tool_profile=[])
        assert result.result.model_dump(mode='json') == corrected
        assert len(requests) == len(ledger.list_calls()) == 2
        feedback = requests[1]['messages'][1]['content']
        assert 'STOP_requires_card_candidate_null' in feedback
        assert 'use_CONTINUE_to_submit_candidate' in feedback
        assert store.get_task('task_fixture').status == 'ACCEPTED'
    finally:
        await runtime.close()
