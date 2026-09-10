from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pytest
from arc.pricing import PriceBook

# Preserve the original cost expectations for historical V4 records.
PRICES = Path(__file__).parents[1] / 'configs/pricing-2026-09-07.json'

def test_tariff_boundary_and_reasoning_is_not_double_billed():
    p = PriceBook(PRICES)
    cost = p.cost('deepseek-v4-pro', {'prompt_tokens': 1000000, 'prompt_cache_hit_tokens': 200000,
        'prompt_cache_miss_tokens': 800000, 'completion_tokens': 100000,
        'completion_tokens_details': {'reasoning_tokens': 90000}},
        datetime.fromisoformat('2026-09-07T08:59:00+08:00'), datetime.fromisoformat('2026-09-07T09:01:00+08:00'))
    assert cost.lower == Decimal('4.98')
    assert cost.upper == Decimal('9.96')
    assert cost.status == 'usage_calculated'

def test_missing_cache_and_usage_keep_conservative_upper():
    p = PriceBook(PRICES)
    at = datetime.fromisoformat('2026-09-07T10:00:00+08:00')
    cost = p.cost('deepseek-v4-flash', {'prompt_tokens': 1000000, 'completion_tokens': 0}, at, at)
    assert (cost.lower,cost.upper,cost.status) == (Decimal('.1'),Decimal('3'),'bounded_estimate')
    assert p.cost('deepseek-v4-pro', None, at, at).upper == p.admission_bound('deepseek-v4-pro')

def test_full_context_joint_upper_covers_both_long_input_and_long_output():
    p = PriceBook(PRICES)
    for model in ['deepseek-v4-flash','deepseek-v4-pro']:
        config = p.model(model); r=p.rates(model,'peak')
        for output in [0, 1, 100000, config['max_output_tokens']]:
            input_tokens=config['context_tokens']-output
            actual=(input_tokens*r['miss']+output*r['output'])/Decimal(1000000)
            assert actual <= p.admission_bound(model)
        assert p.maximum_output(model)==384000
    with pytest.raises(ValueError,match='MODEL_NOT_ALLOWED'):p.admission_bound('other')

def test_invalid_cache_and_naive_dates_rejected():
    p=PriceBook(PRICES);at=datetime.fromisoformat('2026-09-07T10:00:00+08:00')
    with pytest.raises(ValueError,match='CACHE_USAGE_INVALID'):
        p.cost('deepseek-v4-flash',{'prompt_tokens':10,'completion_tokens':1,'prompt_cache_hit_tokens':3,'prompt_cache_miss_tokens':6},at,at)
    with pytest.raises(ValueError,match='TIMEZONE_REQUIRED'):p.period(datetime(2026,9,7))
