"""Current V4.1 defaults, exact tariffs and actual SDK wire contract (offline)."""
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from arc.config import Settings, load_settings
from arc.model_adapters import CURRENT_RESEARCH_ALIAS, CURRENT_API_MODEL, default_models
from arc.pricing import PriceBook
from tests.test_runtime import setup_runtime, invoke, sse, answer

ROOT = Path(__file__).parents[1]


def test_every_new_role_uses_one_current_alias_and_correct_api_id():
    for settings in (Settings(), load_settings(ROOT / 'configs/runtime.yaml')):
        assert settings.research_model == CURRENT_RESEARCH_ALIAS == 'deepseek-flash'
        assert set(settings.models) == {CURRENT_RESEARCH_ALIAS}
        assert set(settings.roles.values()) == {CURRENT_RESEARCH_ALIAS}
        model = settings.models[CURRENT_RESEARCH_ALIAS]
        assert model.model == CURRENT_API_MODEL == 'deepseek-flash'
        assert model.reasoning_effort == 'max' and model.thinking == 'enabled'
        assert model.capabilities.max_output_tokens == 384000


def test_new_price_snapshot_keeps_historical_snapshot_and_exact_crossed_tariff_cost():
    prices = PriceBook(ROOT / 'configs/pricing.json')
    assert set(prices.snapshot['models']) == {'deepseek-flash'}
    assert prices.snapshot['models']['deepseek-flash']['announced_version'] == 'DeepSeek-V4.1-Flash'
    usage = {'prompt_tokens': 1000000, 'prompt_cache_hit_tokens': 200000,
        'prompt_cache_miss_tokens': 800000, 'completion_tokens': 100000,
        'completion_tokens_details': {'reasoning_tokens': 90000}}
    start = datetime.fromisoformat('2026-09-10T08:59:00+08:00')
    end = datetime.fromisoformat('2026-09-10T09:01:00+08:00')
    cost = prices.cost('deepseek-flash', usage, start, end)
    assert (cost.lower, cost.upper, cost.status) == (Decimal('1.204'), Decimal('2.408'), 'usage_calculated')
    old = PriceBook(ROOT / 'configs/pricing-2026-09-07.json')
    assert old.snapshot_id == 'deepseek-cny-2026-09-07'
    old_cost = old.cost('deepseek-v4-pro', usage, start, end)
    assert (old_cost.lower, old_cost.upper) == (Decimal('4.98'), Decimal('9.96'))
    with pytest.raises(ValueError, match='MODEL_NOT_ALLOWED:deepseek-v4-pro'):
        prices.cost('deepseek-v4-pro', usage, start, end)


def test_new_admission_bound_covers_full_context_and_missing_usage_without_lowering_output():
    prices = PriceBook(ROOT / 'configs/pricing.json')
    assert prices.admission_bound('deepseek-flash') == Decimal('4.304')
    assert prices.maximum_output('deepseek-flash') == 384000
    for output in (0, 1, 100000, 384000):
        actual = (Decimal(1000000 - output) * 2 + Decimal(output) * 8) / 1000000
        assert actual <= prices.admission_bound('deepseek-flash')
    at = datetime.fromisoformat('2026-09-10T10:00:00+08:00')
    unknown_cache = prices.cost('deepseek-flash', {'prompt_tokens': 1000000, 'completion_tokens': 0}, at, at)
    assert (unknown_cache.lower, unknown_cache.upper) == (Decimal('.04'), Decimal('2'))
    assert prices.cost('deepseek-flash', None, at, at).upper == Decimal('4.304')


@pytest.mark.asyncio
async def test_current_actual_sdk_model_alias_accounting_and_cached_resume(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [sse(json.dumps(answer()), model='deepseek-flash')])
    runtime.models = default_models()
    runtime.role_models = {'investigator': CURRENT_RESEARCH_ALIAS}
    runtime.prices = PriceBook(ROOT / 'configs/pricing.json')
    result = await invoke(runtime)
    assert result.result.value == 'valid' and len(requests) == 1
    request = requests[0]
    assert request['model'] == 'deepseek-flash'
    assert request['thinking'] == {'type': 'enabled'} and request['reasoning_effort'] == 'max'
    assert request['max_tokens'] == 384000
    call = ledger.list_calls('stage')[0]
    assert call['state'] == 'SETTLED'
    assert call['metadata']['model_alias'] == 'deepseek-flash'
    assert call['metadata']['model_requested'] == 'deepseek-flash'
    assert call['metadata']['announced_version'] == 'DeepSeek-V4.1-Flash'
    assert store.get_task('task_fixture').model_id == 'deepseek-flash'
    balance = ledger.summary('stage')
    await invoke(runtime)
    assert len(requests) == 1 and ledger.summary('stage') == balance
    await runtime.close()


@pytest.mark.asyncio
async def test_old_frozen_model_is_not_silently_rebound_or_bought_with_new_prices(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    runtime.prices = PriceBook(ROOT / 'configs/pricing.json')
    with pytest.raises(ValueError, match='MODEL_NOT_ALLOWED:deepseek-v4-flash:price_snapshot='):
        await invoke(runtime)
    assert requests == [] and ledger.summary('stage')['call_count'] == 0
    assert runtime.role_models == {'investigator': 'deepseek-v4-flash'}
    await runtime.close()
