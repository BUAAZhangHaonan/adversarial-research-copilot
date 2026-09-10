"""Best-effort wallet visibility and transparent token-based planning estimates.

No model calls, budget mutations, approvals, or changes to historical accounting.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, UTC
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from pathlib import Path
import re

import httpx

from .pricing import PriceBook

# Total tokens across requests in one semantic task, not generation limits.
# These deliberately broad fallbacks are planning assumptions, not measurements.
TOKEN_ASSUMPTIONS = {
    'survey': (80000, 500000, 8000, 50000),
    'sketch': (10000, 35000, 2000, 12000),
    'triage': (8000, 30000, 1000, 8000),
    'check': (80000, 400000, 8000, 40000),
    'prestudy': (80000, 400000, 8000, 40000),
    'polish': (8000, 40000, 1000, 10000),
}


def money(value):
    return format(Decimal(value).quantize(Decimal('0.000001')), 'f')


def phase_for_task(task_id):
    if task_id.endswith(('.survey', '.survey.refresh')): return 'survey'
    for phase in ('sketch', 'triage', 'check', 'prestudy', 'polish'):
        if task_id.endswith('.' + phase) or task_id.endswith('.stage_' + phase): return phase
    return None


def _usage_cost(prices, model, usage, period, upper):
    rates = prices.rates(model, period)
    prompt, output = usage['prompt_tokens'], usage['completion_tokens']
    hit, miss = usage.get('prompt_cache_hit_tokens'), usage.get('prompt_cache_miss_tokens')
    if type(hit) is int and type(miss) is int and min(hit, miss) >= 0 and hit + miss == prompt:
        input_cost = hit * rates['hit'] + miss * rates['miss']
    else:
        input_cost = prompt * rates['miss' if upper else 'hit']
    return (input_cost + output * rates['output']) / Decimal(1000000)


def empirical_tasks(store, ledger, prices, model):
    """Only fully accepted tasks of this API model; reprice tokens, never old bills."""
    if store is None or ledger is None: return {}
    grouped = defaultdict(list)
    for call in ledger.list_calls():
        if call.get('state') != 'SETTLED' or call.get('model_requested') != model: continue
        usage = call.get('metadata', {}).get('usage') or {}
        if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('prompt_tokens', 'completion_tokens')): continue
        task_id = call.get('task_id')
        if not isinstance(task_id, str) or phase_for_task(task_id) is None: continue
        grouped[task_id].append(usage)
    costs = defaultdict(list)
    for task_id, usages in grouped.items():
        task = store.get_task(task_id)
        if task is None or task.status != 'ACCEPTED': continue
        costs[phase_for_task(task_id)].append((
            sum((_usage_cost(prices, model, u, 'off_peak', False) for u in usages), Decimal(0)),
            sum((_usage_cost(prices, model, u, 'peak', True) for u in usages), Decimal(0))))
    return costs


def planned_tasks(mode, draws, polish=True, state=None):
    state = state or {}
    if mode not in {'discover', 'develop', 'run'}: raise ValueError('PREFLIGHT_STAGE_UNSUPPORTED')
    if not 1 <= draws <= 5: raise ValueError('PREFLIGHT_DRAWS_OUT_OF_RANGE')
    counts = {phase: [0, 0] for phase in TOKEN_ASSUMPTIONS}
    if mode == 'discover':
        counts['survey'] = [0, 0] if (state.get('field_brief') or state.get('survey')) else [1, 1]
        if state.get('survey_refresh_used') and not (state.get('survey_refresh_applied') or state.get('survey.refresh')):
            counts['survey'][0] += 1; counts['survey'][1] += 1
        stopped = any(value.get('action') == 'stop' for key, value in state.items()
                      if re.fullmatch(r'idea\d+\.sketch', key) and isinstance(value, dict))
        for ordinal in range(1, draws + 1):
            key = f'idea{ordinal}'
            if stopped or state.get(key + '_done'): continue
            sketch = state.get(key + '.sketch')
            triage = state.get(key + '.triage')
            if not sketch: counts['sketch'] = [n + 1 for n in counts['sketch']]
            if sketch and sketch.get('action') != 'submit': continue
            if not triage: counts['triage'] = [n + 1 for n in counts['triage']]
            if triage and triage.get('action') != 'investigate': continue
            if not state.get(key + '.check'):
                counts['check'][1] += 1
                if triage: counts['check'][0] += 1
    elif not state.get('prestudy'):
        counts['prestudy'] = [1, 1]
    if polish and not (state.get('polish') or state.get('stage_polish')):
        counts['polish'] = [1, 1]
    return counts


def estimate_stage(settings, prices, *, store=None, ledger=None, mode='discover', draws=None,
                   polish=True, state=None):
    draws = settings.draws if draws is None else draws
    counts = planned_tasks(mode, draws, polish, state)
    phase_roles = {'survey': 'scout', 'sketch': 'ideator', 'triage': 'editor',
                   'check': 'scout', 'prestudy': 'scout', 'polish': 'writer'}
    histories, components = {}, []
    for phase, (minimum, maximum) in counts.items():
        if maximum == 0: continue
        role = phase_roles[phase]
        spec = settings.models[settings.roles.get(role, settings.research_model)]
        model = spec.model
        try:
            prices.model(model)
        except ValueError:
            return {'status': 'unavailable', 'reason': 'MODEL_PRICE_NOT_CONFIGURED', 'model': model,
                    'mode': mode, 'draws': draws, 'blocking': False}
        if model not in histories:
            histories[model] = empirical_tasks(store, ledger, prices, model)
        samples = histories[model].get(phase, [])
        if samples:
            low = min(c[0] for c in samples) * Decimal('.75')
            high = max(c[1] for c in samples) * Decimal('1.5')
            basis = 'accepted_same_api_model_usage_repriced_with_0.75_to_1.5_margin'
            token_assumption = None
        else:
            input_low, input_high, output_low, output_high = TOKEN_ASSUMPTIONS[phase]
            low = (input_low * prices.rates(model, 'off_peak')['miss'] + output_low * prices.rates(model, 'off_peak')['output']) / Decimal(1000000)
            high = (input_high * prices.rates(model, 'peak')['miss'] + output_high * prices.rates(model, 'peak')['output']) / Decimal(1000000)
            basis = 'explicit_token_heuristic_no_completed_same_model_sample'
            token_assumption = {'total_input': [input_low, input_high], 'total_output': [output_low, output_high], 'across_all_requests_in_task': True}
        components.append({'phase': phase, 'model': model, 'tasks': [minimum, maximum],
            'lower_cny': money(low * minimum), 'upper_cny': money(high * maximum),
            'basis': basis, 'sample_tasks': len(samples), 'token_assumption': token_assumption})
    lower = sum((Decimal(c['lower_cny']) for c in components), Decimal(0))
    upper = sum((Decimal(c['upper_cny']) for c in components), Decimal(0))
    return {'status': 'estimated', 'mode': mode, 'draws': draws if mode == 'discover' else None,
        'currency': 'CNY', 'lower_cny': money(lower), 'upper_cny': money(upper),
        'price_snapshot_id': prices.snapshot_id, 'components': components,
        'assumptions': ['这是经验/启发范围，不是保证或费用上限；提前 STOP 或淘汰可能更省。',
            '下界按空闲、上界按高峰计价；同模型已完成任务使用原始 usage 重计，不使用旧 Pro 账单。',
            '发现按计划构思次数估计，CHECK 只对入围候选；润色为整个阶段一次。',
            '任务可能包含多次模型请求；完整请求准入上界不作为预计花费。',
            '外部收费工具未计入；检索深度、重试和材料长度可使实际费用超出范围。'],
        'blocking': False}


async def query_deepseek_balance(spec, *, client=None):
    result = {'status': 'unavailable', 'checked_at': datetime.now(UTC).isoformat()}
    if spec.provider != 'deepseek': return {**result, 'reason': 'PROVIDER_BALANCE_UNSUPPORTED'}
    try:
        key = spec.credentials()
    except ValueError:
        return {**result, 'reason': 'CREDENTIALS_UNAVAILABLE'}
    url = spec.endpoint().rstrip('/')
    if url.endswith('/v1'): url = url[:-3]
    async def request(active):
        return await active.get(url + '/user/balance', headers={'Authorization': 'Bearer ' + key}, timeout=8)
    try:
        if client is None:
            async with httpx.AsyncClient(follow_redirects=False) as active:
                response = await request(active)
        else: response = await request(client)
        if response.status_code != 200:
            return {**result, 'reason': 'BALANCE_HTTP_ERROR', 'http_status': response.status_code}
        body = response.json()
        if not isinstance(body, dict): raise ValueError('BALANCE_SCHEMA_INVALID')
        if type(body.get('is_available')) is not bool or not isinstance(body.get('balance_infos'), list):
            raise ValueError('BALANCE_SCHEMA_INVALID')
        if any(not isinstance(item, dict) for item in body['balance_infos']): raise ValueError('BALANCE_SCHEMA_INVALID')
        cny = [item for item in body['balance_infos'] if item.get('currency') == 'CNY']
        total = None
        if len(cny) == 1:
            total = Decimal(cny[0]['total_balance'])
            if not total.is_finite(): raise ValueError('BALANCE_AMOUNT_INVALID')
        return {**result, 'status': 'available', 'is_available': body['is_available'],
            'total_cny': format(total, 'f') if total is not None else None,
            'balance_infos': body['balance_infos']}
    except (httpx.HTTPError, ValueError, TypeError, KeyError, InvalidOperation):
        # Never copy response bodies, credentials or exception messages into logs.
        return {**result, 'reason': 'BALANCE_QUERY_FAILED'}


async def prepare_run_preflight(store, ledger, run, settings, *, polish=True, balance_client=None):
    prices = PriceBook(settings.pricing_path or Path(str(files('arc_config_assets').joinpath('pricing.json'))))
    campaign = store.get_campaign(run.campaign_id) if run.campaign_id else None
    estimate = estimate_stage(settings, prices, store=store, ledger=ledger, mode=run.mode,
        draws=campaign.max_draws if campaign and run.mode == 'discover' else settings.draws,
        polish=polish, state=run.state)
    balance = await query_deepseek_balance(settings.models[settings.research_model], client=balance_client)
    warnings = []
    wallet_exhausted = balance.get('is_available') is False
    total = balance.get('total_cny')
    if total is not None:
        amount = Decimal(total)
        wallet_exhausted = wallet_exhausted or amount <= 0
        if estimate['status'] == 'estimated':
            if amount < Decimal(estimate['lower_cny']): warnings.append('余额低于预计费用范围下界，运行可能中途停止。')
            elif amount < Decimal(estimate['upper_cny']): warnings.append('余额未覆盖预计费用范围上界，运行可能中途停止。')
    elif balance['status'] == 'available': warnings.append('余额未提供唯一人民币余额，无法与人民币预估比较。')
    if balance['status'] != 'available': warnings.append('账户余额查询不可用，仅提供费用预估；继续按现有账本运行。')
    record = {'created_at': datetime.now(UTC).isoformat(), 'run_id': run.run_id,
        'estimate': estimate, 'balance': balance, 'warnings': warnings, 'wallet_exhausted': wallet_exhausted}
    path = f'runs/{run.run_id}/preflight/{datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")}.json'
    store.save_artifact(path, json.dumps(record, ensure_ascii=False, indent=2))
    current = store.get_run(run.run_id)
    store.update_run(run.run_id, state={**current.state, 'preflight': record, 'preflight_artifact_path': path})
    return record


def display_preflight(record):
    # Public console view omits the detailed wallet composition and raw response.
    return {'event': 'run_preflight', 'run_id': record['run_id'], 'estimate': record['estimate'],
        'balance_status': record['balance']['status'], 'balance_cny': record['balance'].get('total_cny'),
        'warnings': record['warnings'], 'wallet_exhausted': record['wallet_exhausted']}
