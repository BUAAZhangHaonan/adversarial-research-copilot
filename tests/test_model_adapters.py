"""Offline adapter substitution, admission errors and provider parameter boundaries."""
import json
from copy import deepcopy

import pytest

from arc.config import Settings, load_settings
from arc.model_adapters import ModelSpec, normalized_usage
from arc.pricing import PriceBook
from arc.runtime import BoundTool, RuntimePaused
from tests.test_runtime import setup_runtime, invoke, sse, answer


def compatible(**overrides):
    return ModelSpec(provider='openai_compatible', model='compatible-research-v1',
        base_url='https://compatible.invalid/v1', api_key_env='ARC_COMPATIBLE_KEY',
        capabilities={'max_output_tokens': 4096}, **overrides)


def install_compatible(runtime):
    spec = compatible()
    runtime.models['research'] = spec
    runtime.role_models['investigator'] = 'research'
    prices = deepcopy(runtime.prices.snapshot)
    # The existing CNY usage adapter can represent a fixed tariff by equal rates.
    # This is a synthetic price fixture, not a claim about a real provider.
    prices['models'][spec.model] = {'announced_version': 'fixture',
        'context_tokens': 8192, 'max_output_tokens': 4096,
        'prices': {p: {'hit': '1', 'miss': '2', 'output': '4'} for p in ('peak', 'off_peak')}}
    runtime.prices = PriceBook.from_bytes(json.dumps(prices).encode())


def test_discover_roles_follow_research_alias_with_explicit_override(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text("research_model: shared\nmodels:\n  shared:\n    provider: openai_compatible\n    model: compatible-research-v1\n    base_url: https://compatible.invalid/v1\n    api_key_env: ARC_COMPATIBLE_KEY\n    capabilities:\n      max_output_tokens: 4096\nroles:\n  editor: deepseek-v4.1-flash\n")
    settings = load_settings(path)
    assert settings.roles['scout'] == settings.roles['ideator'] == 'shared'
    assert settings.roles['editor'] == 'deepseek-v4.1-flash'
    assert settings.models['shared'].reasoning_effort is None
    assert settings.models['shared'].base_url_env is None
    assert {Settings().roles[r] for r in ('scout', 'ideator', 'editor')} == {'deepseek-v4.1-flash'}


@pytest.mark.parametrize('values, error', [
    ({'research_model': 'unconfigured'}, 'UNKNOWN_MODEL_ALIAS'),
    ({'roles': {'scout': 'unconfigured'}}, 'UNKNOWN_MODEL_ALIAS'),
    ({'models': {'other': {'provider': 'unimplemented', 'model': 'x'}}}, 'literal_error'),
])
def test_configuration_rejects_unknown_alias_and_protocol(values, error):
    with pytest.raises(ValueError, match=error):
        Settings(**values)


@pytest.mark.parametrize('values', [
    {'reasoning_effort': 'high'}, {'thinking': 'disabled'},
    {'capabilities': {'max_output_tokens': 64000}},
])
def test_current_provider_capability_never_silently_reduced(values):
    with pytest.raises(ValueError, match='DEEPSEEK_CURRENT'):
        ModelSpec(model='deepseek-v4-pro', **values)


@pytest.mark.asyncio
async def test_compatible_sdk_request_settles_and_resumes_without_provider_fields(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [
        sse(json.dumps(answer()), model='compatible-research-v1')])
    install_compatible(runtime)
    result = await invoke(runtime)
    assert result.result.value == 'valid'
    request = requests[0]
    assert request['model'] == 'compatible-research-v1' and request['max_tokens'] == 4096
    assert 'thinking' not in request and 'reasoning_effort' not in request
    assert 'provider' not in request and 'model_alias' not in request
    assert all('reasoning_content' not in item for item in request['messages'])
    assert request['response_format'] == {'type': 'json_object'}
    assert ledger.list_calls('stage')[0]['state'] == 'SETTLED'
    metadata = ledger.list_calls('stage')[0]['metadata']
    assert metadata['provider'] == 'openai_compatible' and metadata['model_alias'] == 'research'
    assert metadata['effort'] is None and metadata['thinking'] is None
    before = ledger.summary('stage')
    await invoke(runtime)
    assert len(requests) == 1 and ledger.summary('stage') == before
    await runtime.close()


@pytest.mark.asyncio
async def test_missing_configured_credentials_does_not_reserve_or_send(tmp_path, monkeypatch):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    install_compatible(runtime)
    await runtime.client.close()
    runtime.client = None
    monkeypatch.delenv('ARC_COMPATIBLE_KEY', raising=False)
    with pytest.raises(ValueError, match='MODEL_CREDENTIALS_MISSING:ARC_COMPATIBLE_KEY'):
        await invoke(runtime)
    assert ledger.summary('stage')['call_count'] == 0 and requests == []
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['json_output', 'streaming_usage', 'tools'])
async def test_unsupported_operation_rejected_before_admission(tmp_path, operation):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    install_compatible(runtime)
    setattr(runtime.models['research'].capabilities, operation, False)
    kwargs = {}
    if operation == 'tools':
        from decimal import Decimal
        async def handler(arguments, metadata): return {}
        runtime.tools['read_record'] = BoundTool('read_record', {'type': 'object'}, handler,
            Decimal(0), 'OFFLINE_FIXTURE')
        kwargs['tool_profile'] = ['read_record']
    with pytest.raises(ValueError, match='MODEL_OPERATION_UNSUPPORTED'):
        await invoke(runtime, **kwargs)
    assert ledger.summary('stage')['call_count'] == 0 and requests == []
    await runtime.close()


def test_standard_cached_usage_preserves_existing_cost_contract():
    usage = normalized_usage('openai_compatible', {'prompt_tokens': 120,
        'completion_tokens': 30, 'prompt_tokens_details': {'cached_tokens': 40}})
    assert usage['prompt_cache_hit_tokens'] == 40 and usage['prompt_cache_miss_tokens'] == 80


@pytest.mark.asyncio
async def test_alias_rebinding_cannot_change_saved_task_endpoint(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [sse(json.dumps(answer()))])
    await invoke(runtime)
    runtime.models['deepseek-v4-flash'].base_url = 'https://another.invalid'
    runtime.models['deepseek-v4-flash'].base_url_env = None
    with pytest.raises(RuntimePaused, match='TASK_DEPENDENCY_CHANGED'):
        await invoke(runtime)
    assert len(requests) == 1
    await runtime.close()


@pytest.mark.asyncio
async def test_compatible_json_repair_keeps_reasoning_out_of_wire_messages(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [
        sse('{invalid', model='compatible-research-v1'),
        sse(json.dumps(answer()), model='compatible-research-v1')])
    install_compatible(runtime)
    result = await invoke(runtime)
    assert result.result.value == 'valid' and len(requests) == 2
    assert all('reasoning_content' not in message for request in requests for message in request['messages'])
    assert all('thinking' not in request for request in requests)
    assert all(call['state'] == 'SETTLED' for call in ledger.list_calls('stage'))
    await runtime.close()


@pytest.mark.asyncio
async def test_configured_price_output_bound_must_match_capabilities(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    install_compatible(runtime)
    runtime.models['research'].capabilities.max_output_tokens = 8192
    with pytest.raises(ValueError, match='MODEL_PRICING_OUTPUT_LIMIT_MISMATCH'):
        await invoke(runtime)
    assert ledger.summary('stage')['call_count'] == 0 and requests == []
    await runtime.close()


@pytest.mark.parametrize('message', [
    {'role': 'system', 'content': 'Return JSON with the requested fields.'},
    {'role': 'user', 'content': 'Return json.'},
    {'role': 'user', 'content': [{'type': 'text', 'text': 'Return Json.'}]},
])
def test_deepseek_json_keyword_checked_in_actual_system_or_user_prompt(message):
    from arc.model_adapters import request_parameters
    config = {'provider': 'deepseek', 'model': 'deepseek-v4-pro', 'max_tokens': 384000}
    messages = [message]
    request = request_parameters(config, messages, [])
    assert request['messages'] == messages
    assert request['response_format'] == {'type': 'json_object'}


@pytest.mark.parametrize('extra', [
    {'role': 'assistant', 'content': 'JSON'},
    {'role': 'tool', 'content': 'JSON'},
    {'role': 'system', 'content': 'Return the structure.', 'reasoning_content': 'JSON'},
])
def test_deepseek_json_keyword_in_nonprompt_fields_does_not_satisfy_prerequisite(extra):
    from arc.model_adapters import request_parameters
    with pytest.raises(ValueError, match='DEEPSEEK_JSON_PROMPT_KEYWORD_REQUIRED'):
        request_parameters({'provider': 'deepseek'}, [
            {'role': 'user', 'content': 'Repair the missing field.'}, extra], [])


def test_deepseek_json_prerequisite_is_not_imposed_on_other_adapters():
    from arc.model_adapters import request_parameters
    messages = [{'role': 'user', 'content': 'Return the requested structure.'}]
    request = request_parameters({'provider': 'openai_compatible', 'model': 'fixture'}, messages, [])
    assert request['messages'] == messages


@pytest.mark.asyncio
async def test_missing_json_keyword_stops_before_reservation_and_sdk_send(tmp_path):
    from types import SimpleNamespace
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    spec = runtime.models['deepseek-v4-flash']
    config = spec.invocation_config('deepseek-v4-flash', runtime.prices, [])
    state = {'messages': [{'role': 'system', 'content': 'Repair the requested structure.'},
                         {'role': 'user', 'content': 'The required field is missing.'}], 'tools': []}
    with pytest.raises(ValueError, match='DEEPSEEK_JSON_PROMPT_KEYWORD_REQUIRED'):
        await runtime._model_request(SimpleNamespace(), state, config, None)
    assert ledger.summary('stage')['call_count'] == 0 and requests == []
    assert 'pending_model' not in state
    await runtime.close()
