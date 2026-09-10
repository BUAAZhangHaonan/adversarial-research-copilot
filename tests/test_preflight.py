"""No paid requests: estimated token costs, wallet failures, and checkpoint scope."""
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from arc.config import Settings
from arc.cli import new_run, services
from arc.model_adapters import default_models
from arc.preflight import estimate_stage, planned_tasks, query_deepseek_balance, prepare_run_preflight, display_preflight
from arc.pricing import PriceBook

ROOT = Path(__file__).parents[1]


def prices(): return PriceBook(ROOT / 'configs/pricing.json')


def test_default_alias_is_official_name_and_writer_follows_research_model():
    settings = Settings()
    assert settings.research_model == 'deepseek-flash'
    assert set(settings.models) == {'deepseek-flash'}
    assert settings.roles['writer'] == settings.research_model


def test_heuristic_draw_counts_admitted_checks_and_single_stage_polish_are_explicit():
    one = estimate_stage(Settings(draws=1), prices())
    five = estimate_stage(Settings(), prices())
    by_phase = {c['phase']: c for c in five['components']}
    assert by_phase['survey']['tasks'] == [1, 1]
    assert by_phase['sketch']['tasks'] == by_phase['triage']['tasks'] == [5, 5]
    assert by_phase['check']['tasks'] == [0, 5]
    assert by_phase['polish']['tasks'] == [1, 1]
    assert Decimal(five['upper_cny']) > Decimal(one['upper_cny'])
    assert Decimal(one['upper_cny']) != prices().admission_bound('deepseek-flash')
    assert all(c['basis'].startswith('explicit_token_heuristic') for c in five['components'])
    assert all(c['token_assumption']['across_all_requests_in_task'] for c in five['components'])
    for mode in ('develop', 'run'):
        stage = estimate_stage(Settings(), prices(), mode=mode)
        assert [c['phase'] for c in stage['components']] == ['prestudy', 'polish']


def test_checkpoint_estimate_excludes_accepted_work_and_finished_polish():
    state = {'field_brief': {'overview': 'done'}, 'idea1_done': True,
        'idea2.sketch': {'action': 'submit'}, 'idea2.triage': {'action': 'investigate'}, 'polish': {'done': True}}
    plan = planned_tasks('discover', 2, state=state)
    assert plan['survey'] == plan['sketch'] == plan['triage'] == plan['polish'] == [0, 0]
    assert plan['check'] == [1, 1]
    accepted = {'survey': {'overview': 'accepted'}, 'survey_refresh_used': True, 'survey.refresh': {'overview': 'accepted refresh'}}
    assert planned_tasks('discover', 1, state=accepted)['survey'] == [0, 0]
    assert planned_tasks('run', 5, state={'prestudy': {'done': True}, 'polish': {'done': True}}) == {
        phase: [0, 0] for phase in plan}


def test_same_api_model_accepted_usage_is_repriced_and_old_pro_bill_ignored():
    usage = {'prompt_tokens': 10000, 'prompt_cache_hit_tokens': 2000,
        'prompt_cache_miss_tokens': 8000, 'completion_tokens': 1000}
    calls = [{'state': 'SETTLED', 'model_requested': model, 'task_id': task,
        'metadata': {'usage': usage}, 'cost_estimate_upper': '99999'}
        for model, task in [('deepseek-flash', 'new.sketch'), ('deepseek-v4-pro', 'old.sketch'),
                            ('deepseek-flash', 'unfinished.sketch')]]
    ledger = SimpleNamespace(list_calls=lambda: calls)
    store = SimpleNamespace(get_task=lambda task: SimpleNamespace(status='ERROR' if task.startswith('unfinished') else 'ACCEPTED'))
    estimate = estimate_stage(Settings(draws=1), prices(), ledger=ledger, store=store)
    sketch = next(c for c in estimate['components'] if c['phase'] == 'sketch')
    assert sketch['sample_tasks'] == 1
    assert Decimal(sketch['lower_cny']) == Decimal('.01204') * Decimal('.75')
    assert Decimal(sketch['upper_cny']) == Decimal('.02408') * Decimal('1.5')
    assert sketch['token_assumption'] is None


@pytest.mark.asyncio
async def test_balance_endpoint_credentials_not_copied_into_result(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline-private-key')
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={'is_available': True, 'balance_infos': [
            {'currency': 'CNY', 'total_balance': '12.34', 'granted_balance': '2', 'topped_up_balance': '10.34'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await query_deepseek_balance(default_models()['deepseek-flash'], client=client)
    assert requests[0].url.path == '/user/balance' and requests[0].method == 'GET'
    assert requests[0].headers['Authorization'] == 'Bearer offline-private-key'
    assert result['status'] == 'available' and result['total_cny'] == '12.34'
    assert 'offline-private-key' not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['http', 'timeout', 'invalid_json', 'invalid_amount', 'malformed'])
async def test_balance_query_failures_are_nonblocking_and_do_not_echo_response(monkeypatch, failure):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline-private-key')
    def handle(request):
        if failure == 'timeout': raise httpx.ReadTimeout('private diagnostic', request=request)
        if failure == 'http': return httpx.Response(503, text='private diagnostic')
        if failure == 'invalid_json': return httpx.Response(200, text='private diagnostic')
        if failure == 'malformed': return httpx.Response(200, json=['private diagnostic'])
        return httpx.Response(200, json={'is_available': True,
            'balance_infos': [{'currency': 'CNY', 'total_balance': 'NaN'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await query_deepseek_balance(default_models()['deepseek-flash'], client=client)
    assert result['status'] == 'unavailable'
    assert 'private' not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('amount, available, exhausted', [('0.001', True, False), ('0', False, True)])
async def test_private_preflight_saved_without_budget_mutation_low_balance_only_warns(tmp_path, monkeypatch, amount, available, exhausted):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline-private-key')
    settings = Settings(data_dir=tmp_path, draws=1)
    run = new_run(settings, 'discover', topic='A small research topic')
    store, ledger = services(settings)
    before = ledger.summary(run.run_id)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            json={'is_available': available, 'balance_infos': [{'currency': 'CNY', 'total_balance': amount}]}))) as client:
        record = await prepare_run_preflight(store, ledger, run, settings, balance_client=client)
    assert record['warnings'] and record['wallet_exhausted'] is exhausted
    assert ledger.summary(run.run_id) == before
    saved = store.get_run(run.run_id).state
    assert json.loads(store.read_artifact(saved['preflight_artifact_path'])) == record
    public = display_preflight(record)
    assert public['balance_cny'] == amount and 'balance_infos' not in public


@pytest.mark.asyncio
async def test_missing_balance_credentials_still_returns_and_saves_estimate(tmp_path, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    settings = Settings(data_dir=tmp_path)
    run = new_run(settings, 'discover', topic='A small research topic')
    store, ledger = services(settings)
    record = await prepare_run_preflight(store, ledger, run, settings)
    assert record['estimate']['status'] == 'estimated' and not record['wallet_exhausted']
    assert record['balance']['reason'] == 'CREDENTIALS_UNAVAILABLE'
    assert ledger.summary(run.run_id)['call_count'] == 0


@pytest.mark.asyncio
async def test_completed_execute_never_queries_wallet_or_opens_runtime(tmp_path, monkeypatch):
    from arc.cli import execute
    settings = Settings(data_dir=tmp_path)
    run = new_run(settings, 'discover', topic='An already completed topic')
    store, ledger = services(settings)
    store.update_run(run.run_id, status='COMPLETED', stop_reason='finished')
    async def forbidden(*args, **kwargs): raise AssertionError('Completed run must not open providers')
    monkeypatch.setattr('arc.preflight.prepare_run_preflight', forbidden)
    monkeypatch.setattr('arc.bootstrap.make_runtime', forbidden)
    monkeypatch.setattr('arc.reports.render_run', lambda *args: None)
    result = await execute(settings, run.run_id)
    assert result.status == 'COMPLETED' and result.stop_reason == 'finished'
    assert ledger.summary(run.run_id)['call_count'] == 0


@pytest.mark.asyncio
async def test_balance_failure_is_displayed_and_stage_still_starts(tmp_path, monkeypatch, capsys):
    from arc.cli import execute
    settings = Settings(data_dir=tmp_path)
    run = new_run(settings, 'discover', topic='A normal stage')
    store, ledger = services(settings)
    events = []
    async def balance_failure(*args, **kwargs):
        events.append('balance')
        return {'status': 'unavailable', 'reason': 'BALANCE_QUERY_FAILED'}
    async def runtime(*args, **kwargs):
        events.append('runtime')
        return SimpleNamespace()
    async def stage(engine, run_id):
        events.append('stage')
        engine.store.update_run(run_id, status='COMPLETED')
    monkeypatch.setattr('arc.preflight.query_deepseek_balance', balance_failure)
    monkeypatch.setattr('arc.bootstrap.make_runtime', runtime)
    monkeypatch.setattr('arc.workflows.WorkflowEngine.execute', stage)
    monkeypatch.setattr('arc.reports.render_run', lambda *args: None)
    result = await execute(settings, run.run_id)
    assert result.status == 'COMPLETED' and events == ['balance', 'runtime', 'stage']
    assert 'run_preflight' in capsys.readouterr().out
    assert store.get_run(run.run_id).state['preflight']['estimate']['status'] == 'estimated'


@pytest.mark.asyncio
async def test_confirmed_empty_wallet_stops_before_runtime_but_preserves_ledger(tmp_path, monkeypatch):
    from arc.cli import execute
    settings = Settings(data_dir=tmp_path)
    run = new_run(settings, 'discover', topic='A normal stage')
    store, ledger = services(settings)
    before = ledger.summary(run.run_id)
    async def empty(*args, **kwargs):
        return {'status': 'available', 'is_available': False, 'total_cny': '0', 'balance_infos': []}
    async def forbidden(*args, **kwargs): raise AssertionError('Empty wallet must not start requests')
    monkeypatch.setattr('arc.preflight.query_deepseek_balance', empty)
    monkeypatch.setattr('arc.bootstrap.make_runtime', forbidden)
    monkeypatch.setattr('arc.reports.render_run', lambda *args: None)
    result = await execute(settings, run.run_id)
    assert result.status == 'PAUSED_BUDGET' and result.stop_reason == 'provider_wallet_unavailable'
    assert ledger.summary(run.run_id) == before
