from copy import deepcopy
import json
import pytest
from arc.runtime import RuntimePaused
from arc.schemas import SelectorResult
from tests.test_runtime import answer, setup_runtime, sse
from tests.test_selection import research_store, research_draft, novelty_result, selection_result


def fixture(tmp_path, repeated=False):
    bad = selection_result()
    bad.selection_checks.resource_path.status = 'unknown'
    bad.selection_checks.test_identifiability.status = 'unknown'
    valid = selection_result('LEAD_ONLY', selection_checks=bad.selection_checks.model_dump())
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses)
    research_store(tmp_path)
    card = store.save_card(research_draft())
    subject = {'campaign_id': None, 'run_id': 'run_fixture', 'card_id': card.card_id, 'card_version': card.version}
    store.update_run('run_fixture', card_id=card.card_id, card_version=card.version)
    payload = {'card': card.model_dump(mode='json'), 'novelty': novelty_result().model_dump(mode='json')}
    for judgment in [bad, bad if repeated else valid]:
        envelope = answer(); envelope['subject'] = subject; envelope['result'] = judgment.model_dump(mode='json')
        responses.append(sse(json.dumps(envelope), model='deepseek-v4-pro'))
    runtime.role_models['selector'] = 'deepseek-v4-pro'
    return runtime, store, requests, payload, subject, valid


@pytest.mark.asyncio
@pytest.mark.parametrize('repeated', [False, True])
async def test_selector_contract_uses_one_json_correction_with_all_status_locations(tmp_path, repeated):
    runtime, store, requests, payload, subject, valid = fixture(tmp_path, repeated)
    try:
        if repeated:
            with pytest.raises(RuntimePaused, match='INVALID_OUTPUT_AFTER_REPAIR'):
                await runtime.invoke('selector', 'INVOKE', payload, SelectorResult, subject, 'task_fixture', tool_profile=[])
            assert store.get_task('task_fixture').accepted_result is None
        else:
            result = await runtime.invoke('selector', 'INVOKE', payload, SelectorResult, subject, 'task_fixture', tool_profile=[])
            assert result.result == valid
            assert result.result.selection_checks.resource_path.status == 'unknown'
        assert len(requests) == 2
        correction = requests[1]['messages'][1]['content']
        assert 'MAIN_REPORT_PREREQUISITE_UNESTABLISHED' in correction
        assert 'resource_path' in correction and 'test_identifiability' in correction
        state = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        assert state['repair_counts']['output_json'] == 1
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_saved_selector_response_resume_buys_only_the_correction(tmp_path):
    runtime, store, requests, payload, subject, valid = fixture(tmp_path)
    original = runtime._validate_output_contracts
    def old_pause(*args):
        raise RuntimePaused('PAUSED_PROTOCOL', 'OLD_POST_ACCEPT_CONTRACT')
    runtime._validate_output_contracts = old_pause
    try:
        with pytest.raises(RuntimePaused):
            await runtime.invoke('selector', 'INVOKE', payload, SelectorResult, subject, 'task_fixture', tool_profile=[])
        assert len(requests) == 1
        runtime._validate_output_contracts = original
        result = await runtime.invoke('selector', 'INVOKE', payload, SelectorResult, subject, 'task_fixture', tool_profile=[])
        assert result.result == valid and len(requests) == 2
    finally:
        await runtime.close()
