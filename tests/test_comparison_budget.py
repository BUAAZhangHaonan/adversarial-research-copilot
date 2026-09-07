import pytest
from arc.budget import BudgetLedger
from arc.evaluation import VALIDATION_PARENT, run_comparison
from tests.test_evaluation import environment

@pytest.mark.asyncio
async def test_comparison_preserves_extended_parent_and_uses_configured_new_stage_limit(tmp_path, monkeypatch):
    settings, store, source, calls = environment(tmp_path, monkeypatch)
    settings = settings.model_copy(update={'budget_cny': '50'})
    ledger = BudgetLedger(store.db_path)
    ledger.create_account(VALIDATION_PARENT, '285')
    result = await run_comparison(settings, source.run_id)
    assert result['comparison_status'] == 'completed'
    assert ledger.summary(VALIDATION_PARENT)['limit_cny'] == '285.000000'
    for suffix in ('ARC', 'direct-Pro', 'evaluator'):
        assert ledger.summary(source.run_id + '.comparison.' + suffix)['limit_cny'] == '50.000000'
    await run_comparison(settings.model_copy(update={'budget_cny': '80'}), source.run_id)
    for suffix in ('ARC', 'direct-Pro', 'evaluator'):
        assert ledger.summary(source.run_id + '.comparison.' + suffix)['limit_cny'] == '50.000000'
