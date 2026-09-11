import json
from decimal import Decimal
import pytest
from arc.external_cost import service_cost, cost_for_model
from arc.budget import BudgetLedger, BudgetError
from arc.runtime import BoundTool
from tests.test_runtime import setup_runtime, sse, answer, invoke


def cost(**updates):
    return dict(schema_version='mcp.cost.v1', currency='CNY', scope='provider_api_only',
        basis='estimated_usage', lower_cny='0.012345', upper_cny='0.012345', total_cny='0.012345',
        complete=True, model_calls=1, unknown_calls=0, attempts=[{'request_id':'remote1'}],
        reused_result=False, **updates)


@pytest.mark.parametrize('updates', [dict(currency='USD'), dict(lower_cny='NaN'),
    dict(upper_cny='-1'), dict(complete=True, unknown_calls=1), dict(model_calls=True),
    dict(total_cny='9'), dict(upper_cny=None), dict(basis='invoice')])
def test_invalid_service_cost_is_not_zero(updates):
    value=cost();value.update(updates)
    assert service_cost(value) is None


def test_partial_usage_remains_unknown_and_cache_is_incremental_zero():
    value=cost();value.update(complete=False, upper_cny=None, total_cny=None, unknown_calls=1, basis='partial_usage')
    assert service_cost(value)['upper_cny'] is None
    cached=cost();cached.update(basis='no_paid_calls', lower_cny='0', upper_cny='0', total_cny='0', model_calls=0, reused_result=True)
    assert service_cost(cached)['total_cny']=='0'


def test_complete_service_cost_counts_once_without_invoice_claim(tmp_path):
    ledger=BudgetLedger(tmp_path/'state.sqlite');ledger.create_account('stage','100')
    ledger.register_unmetered('stage','external1',allow_unmetered=True,service='scholartrace',method='search_literature')
    ledger.mark_started('external1')
    for _ in range(2):ledger.finish_unmetered('external1',reported_cost=cost())
    assert ledger.summary('stage')['spent_upper_cny']=='0.012345'
    assert ledger.get_call('external1')['cost_status']=='service_reported_usage'
    assert ledger.get_call('external1')['cost_actual_if_available'] is None
    with pytest.raises(BudgetError):ledger.finish_unmetered('external1',reported_cost=None)


@pytest.mark.asyncio
async def test_cost_attempts_preserved_in_trace_and_compacted_in_model_context(tmp_path):
    async def search(arguments, metadata):return {'source_ids':[], 'cost':cost()}
    tool=BoundTool('search_literature',{'type':'object','properties':{'query':{'type':'string'}},'required':['query']},
        search,None,'COST_UNOBSERVABLE','scholartrace',False,True)
    parts=[{'index':0,'id':'external1','type':'function','function':{'name':'search_literature','arguments':'{"query":"visual hallucination"}'}}]
    runtime,store,ledger,requests=setup_runtime(tmp_path,[sse(finish='tool_calls',tools=parts),sse(json.dumps(answer()))],tools={'search_literature':tool})
    await invoke(runtime,tool_profile=['search_literature'])
    message=json.loads(requests[1]['messages'][-1]['content'])
    assert 'attempts' not in message['cost']
    assert runtime.tool_trace('task_fixture')[0]['result']['cost']['attempts']==[{'request_id':'remote1'}]
    assert message['external_cost']['status']=='service_reported_usage'
    await runtime.close()
