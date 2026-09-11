"""Unmetered external actions are not zero-price financial estimates."""
import pytest
from arc.budget import BudgetError, BudgetLedger


def test_unmetered_accounting_does_not_assert_a_zero_price_or_consume_model_budget(tmp_path):
    ledger = BudgetLedger(tmp_path / 'state.sqlite')
    ledger.create_account('parent', '1')
    ledger.create_account('child', '1', parent_id='parent')
    with pytest.raises(BudgetError, match='not_authorized'):
        ledger.register_unmetered('child', 'forbidden', allow_unmetered=True, service='other', method='query')
    metadata = dict(allow_unmetered=True, service='scholartrace', method='search_literature')
    pending = ledger.register_unmetered('child', 'external', **metadata)
    assert pending['cost_estimate_lower'] is pending['cost_estimate_upper'] is pending['reserved_cny'] is None
    ledger.mark_started('external')
    done = ledger.finish_unmetered('external')
    assert done['state'] == 'SETTLED' and done['cost_status'] == 'unmetered'
    assert done['upper_micro'] is done['lower_micro'] is None
    summary = ledger.summary('parent')
    assert summary['unmetered_calls'] == 1 and summary['total_cost_complete'] is False
    assert summary['cost_scope'] == 'metered_costs_only' and summary['unknown_calls'] == 0
    assert summary['remaining_cny'] == '1.000000'
    ledger.reserve('child', 'model', '1')
    ledger.mark_started('model')
    ledger.settle('model', '.25', '.25', 'usage_calculated')
    assert ledger.summary('parent')['spent_upper_cny'] == '0.250000'
