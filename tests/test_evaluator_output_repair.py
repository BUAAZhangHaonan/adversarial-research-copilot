"""Evaluator candidate addressing uses one JSON repair, not forced preferences."""
from copy import deepcopy
import json

import pytest

from arc.runtime import RuntimePaused
from arc.schemas import EvaluatorResult
from tests.test_runtime import SUBJECT, answer, setup_runtime, sse


def judgment(identifiers):
    return {'per_candidate_findings': [{'candidate_id': identifier,
        'findings': ['No research card was produced; quality cannot be assessed.'],
        'evidence_ids': []} for identifier in identifiers],
        'decisive_errors': [], 'supported_strengths': [],
        'unresolved_verifications': ['No candidate result supports a comparison.'],
        'preference_if_requested': None, 'uncertainty': 'Inconclusive: no research cards.'}


def response(result):
    envelope = answer()
    envelope['result'] = result
    return sse(json.dumps(envelope), model='deepseek-v4-pro')


async def invoke(runtime, candidates):
    return await runtime.invoke('evaluator', 'INVOKE', {'candidates': candidates},
        EvaluatorResult, SUBJECT, 'task_fixture', tool_profile=[])


@pytest.mark.asyncio
@pytest.mark.parametrize('error', ['missing', 'duplicate', 'unknown'])
async def test_evaluator_coverage_is_corrected_once_before_acceptance_without_changing_judgments(tmp_path, error):
    ids = ['candidate_1', 'candidate_2']
    candidates = [{'candidate_id': identifier, 'research_card': None} for identifier in ids]
    valid = judgment(ids)
    malformed = deepcopy(valid)
    if error == 'missing':
        malformed['per_candidate_findings'].pop()
    elif error == 'duplicate':
        malformed['per_candidate_findings'].append(deepcopy(malformed['per_candidate_findings'][0]))
    else:
        malformed['per_candidate_findings'][1]['candidate_id'] = 'candidate_unknown'
    runtime, store, ledger, requests = setup_runtime(tmp_path, [response(malformed), response(valid)])
    runtime.role_models['evaluator'] = 'deepseek-v4-pro'
    try:
        result = await invoke(runtime, candidates)
        assert result.result.model_dump(mode='json') == valid
        assert len(requests) == len(ledger.list_calls()) == 2
        feedback = requests[1]['messages'][1]['content']
        for field in ['EVALUATOR_CANDIDATE_COVERAGE', 'expected', 'supplied', 'missing', 'duplicate']:
            assert field in feedback
        assert error in feedback
        assert store.get_task('task_fixture').status == 'ACCEPTED'
    finally:
        await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('identifiers', [[], ['candidate_1', 'candidate_2']])
async def test_no_cards_inconclusive_is_accepted_without_forcing_preference(tmp_path, identifiers):
    valid = judgment(identifiers)
    candidates = [{'candidate_id': identifier, 'research_card': None} for identifier in identifiers]
    runtime, store, ledger, requests = setup_runtime(tmp_path, [response(valid)])
    runtime.role_models['evaluator'] = 'deepseek-v4-pro'
    try:
        result = await invoke(runtime, candidates)
        assert len(requests) == 1 and result.result.preference_if_requested is None
        assert result.result.model_dump(mode='json') == valid
        assert store.get_task('task_fixture').status == 'ACCEPTED'
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_evaluator_coverage_does_not_add_another_allowance_after_json_repair(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path,
        [sse('{broken', model='deepseek-v4-pro'), response(judgment([]))])
    runtime.role_models['evaluator'] = 'deepseek-v4-pro'
    try:
        with pytest.raises(RuntimePaused, match='INVALID_OUTPUT_AFTER_REPAIR'):
            await invoke(runtime, [{'candidate_id': 'candidate_1', 'research_card': None}])
        assert len(requests) == 2 and store.get_task('task_fixture').accepted_result is None
        state = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        assert 'candidate_1' in str(state['final_validation_errors'])
    finally:
        await runtime.close()
