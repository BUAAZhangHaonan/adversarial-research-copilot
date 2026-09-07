from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from arc.budget import BudgetLedger, BudgetError, BudgetExceeded, to_micro

@pytest.fixture
def ledger(tmp_path):
    value=BudgetLedger(tmp_path/"arc.sqlite")
    value.create_account("dev",100)
    value.create_account("discover",20,"dev")
    return value

def test_five_draws_share_one_stage_budget_and_resume(ledger):
    for index in range(5):
        ledger.reserve("discover",f"draw{index}",4)
        ledger.mark_started(f"draw{index}")
        ledger.settle(f"draw{index}",4,4,"usage_calculated")
    restarted=BudgetLedger(ledger.db_path)
    assert restarted.summary("discover")["remaining_micro"]==0
    with pytest.raises(BudgetExceeded): restarted.reserve("discover","sixth",1)
    assert restarted.summary("dev")["spent_upper_cny"]=="20.000000"

def test_parent_includes_all_child_stages_and_own_calls(ledger):
    for name in ["develop","run"]: ledger.create_account(name,20,"dev")
    ledger.reserve("dev","baseline",50)
    for name in ["discover","develop"]: ledger.reserve(name,name,20)
    with pytest.raises(BudgetExceeded): ledger.reserve("run","run",20)
    assert ledger.summary("dev")["remaining_cny"]=="10.000000"

def test_unknown_attempt_preserves_reservation_and_retry_is_separate(ledger):
    ledger.reserve("discover","a",12); ledger.mark_started("a")
    ledger.settle("a",0,None,"unknown",error="stream interrupted")
    assert ledger.summary("discover")["unknown_calls"]==1
    assert ledger.summary("discover")["reserved_cny"]=="12.000000"
    with pytest.raises(BudgetExceeded): ledger.reserve("discover","retry",12)
    ledger.settle("a",2,3,"usage_calculated")
    ledger.reserve("discover","retry",12)
    assert ledger.summary("dev")["remaining_cny"]=="85.000000"

def test_settlement_idempotency_does_not_double_charge(ledger):
    ledger.reserve("discover","a",10); ledger.mark_started("a")
    ledger.settle("a",Decimal("0.123456"),Decimal("0.123456"),"usage_calculated")
    ledger.settle("a",Decimal("0.123456"),Decimal("0.123456"),"usage_calculated")
    assert ledger.summary("dev")["spent_upper_micro"]==123456
    with pytest.raises(BudgetError): ledger.settle("a",1,1,"usage_calculated")

def test_integer_micro_rounding_is_conservative(ledger):
    assert to_micro("0.0000001")==1
    assert to_micro("0.0000009",upper=False)==0
    for number in range(100):
        ledger.reserve("discover",str(number),"0.000001")
        ledger.settle(str(number),"0.000001","0.000001","usage_calculated")
    assert ledger.summary("discover")["spent_upper_micro"]==100

def test_zero_or_unbounded_cost_not_silently_inferred(ledger):
    with pytest.raises(Exception): ledger.reserve("discover","x",None)
    ledger.reserve("discover","a",3)
    with pytest.raises(ValueError): ledger.settle("a",0,None,"usage_calculated")

def test_only_unsent_requests_release_without_charge(ledger):
    ledger.reserve("discover","a",10); ledger.mark_not_sent("a")
    assert ledger.summary("discover")["remaining_micro"]==20_000_000
    ledger.reserve("discover","b",10); ledger.mark_started("b")
    with pytest.raises(BudgetError): ledger.mark_not_sent("b")
    with pytest.raises(BudgetError): ledger.mark_started("b")

def test_authorization_cannot_reset_on_resume_or_escape_parent(ledger):
    ledger.reserve("discover","a",12)
    with pytest.raises(BudgetError): ledger.create_account("discover",40,"dev")
    ledger.add_budget("discover",5,"explicit user authorization")
    assert ledger.summary("discover")["remaining_cny"]=="13.000000"
    with pytest.raises(BudgetError): ledger.add_budget("discover",100,"cannot expand parent")

def test_transaction_prevents_two_accounts_overreserving_parent(tmp_path):
    ledger=BudgetLedger(tmp_path/"arc.sqlite"); ledger.create_account("root",10)
    ledger.create_account("one",10,"root"); ledger.create_account("two",10,"root")
    def attempt(name):
        try: BudgetLedger(ledger.db_path).reserve(name,name,8); return True
        except BudgetExceeded: return False
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(attempt,["one","two"]))
    assert sum(results)==1
    assert ledger.summary("root")["reserved_micro"]==8_000_000

def test_observed_bill_overrun_is_recorded_and_blocks_next_request(ledger):
    ledger.reserve("discover","a",10)
    ledger.settle("a",21,21,"measured_invoice")
    assert ledger.get_call("a")["metadata"]["admission_bound_exceeded"] is True
    assert ledger.summary("discover")["remaining_cny"]=="-1.000000"
    with pytest.raises(BudgetExceeded): ledger.reserve("discover","b",0)

def test_unknown_lower_bound_does_not_make_known_cost_interval_inverted(ledger):
    ledger.reserve("discover","uncertain",8)
    ledger.mark_started("uncertain")
    ledger.settle("uncertain",2,8,"unknown")
    summary=ledger.summary("discover")
    assert summary["spent_lower_micro"]<=summary["spent_upper_micro"]
    assert summary["unsettled_lower_micro"]==2_000_000
    assert summary["reserved_micro"]==8_000_000 and summary["remaining_micro"]==12_000_000

def test_request_price_and_subject_cannot_change_when_settling(ledger):
    ledger.reserve("discover","a",5,run_id="r1",price_snapshot_id="original")
    with pytest.raises(BudgetError): ledger.reserve("discover","a",5,run_id="r2")
    with pytest.raises(BudgetError): ledger.settle("a",1,1,"usage_calculated",price_snapshot_id="updated")
    assert ledger.get_call("a")["price_snapshot_id"]=="original"

def test_call_ledger_preserves_full_usage_and_does_not_invent_actual_invoice(ledger):
    ledger.reserve("discover","a",5,run_id="r",stage="discover",task_id="t",model_requested="deepseek-v4-pro",thinking="enabled",effort="max",price_snapshot_id="prices",prompt_hash="hash",attempt=0)
    ledger.settle("a","0.001","0.002","usage_calculated",usage={"prompt_tokens":100,"prompt_cache_hit_tokens":20,"prompt_cache_miss_tokens":80,"completion_tokens":50,"completion_tokens_details":{"reasoning_tokens":30}},request_id="provider-id",model_returned="deepseek-v4-pro",finish_reason="stop")
    call=ledger.get_call("a")
    assert call["input_tokens"]==100 and call["reasoning_tokens"]==30
    assert call["completion_tokens"]==50 and call["attempt_id"]=="a"
    assert call["cost_actual_if_available"] is None and call["currency"]=="CNY"
    assert call["effort"]=="max" and call["stage"]=="discover"

def test_invoice_cannot_be_an_estimated_range(ledger):
    ledger.reserve("discover","a",3)
    with pytest.raises(ValueError): ledger.settle("a",1,2,"measured_invoice")
