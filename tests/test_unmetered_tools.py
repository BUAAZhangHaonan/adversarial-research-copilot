"""Authorized ScholarTrace costs remain unknown without blocking model accounting."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from arc.budget import BudgetError, BudgetLedger
from arc.runtime import BoundTool
from tests.test_runtime import setup_runtime, sse, answer, invoke




@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [False, True])
async def test_authorized_tool_result_or_timeout_allows_next_model_response(tmp_path, failure):
    seen = []
    async def search(arguments, metadata):
        seen.append(arguments)
        if failure:
            raise TimeoutError('upstream timeout')
        return {'source_ids': [], 'results': [{'title': 'Relevant literature'}]}
    tool = BoundTool('search_literature', {'type': 'object', 'properties': {'query': {'type': 'string'}},
        'required': ['query']}, search, None, 'COST_UNOBSERVABLE', 'scholartrace', False, True)
    parts = [{'index': 0, 'id': 'external1', 'type': 'function',
        'function': {'name': 'search_literature', 'arguments': '{"query":"visual hallucination"}'}}]
    runtime, store, ledger, requests = setup_runtime(tmp_path,
        [sse(finish='tool_calls', tools=parts), sse(json.dumps(answer()))], tools={'search_literature': tool})
    result = await invoke(runtime, tool_profile=['search_literature'])
    assert result.result.value == 'valid' and len(requests) == 2 and len(seen) == 1
    external = next(call for call in ledger.list_calls() if call['tool_call_id'])
    assert external['state'] == 'SETTLED' and external['cost_status'] == 'unmetered'
    assert external['cost_estimate_lower'] is external['cost_estimate_upper'] is None
    assert external['outcome_status'] == ('unmetered_outcome_unknown' if failure else 'response_received')
    assert ledger.summary('parent')['unknown_calls'] == 0
    reply = json.loads(requests[1]['messages'][-1]['content'])
    assert reply['external_cost']['upper_cny'] is None
    if failure:
        assert reply['is_error'] and reply['error'] == 'UNMETERED_TOOL_OUTCOME_UNKNOWN'
    # Cached task reuse must not issue the external action again.
    await invoke(runtime, tool_profile=['search_literature'])
    assert len(seen) == 1
    await runtime.close()


def test_packaged_authorization_is_only_for_scholartrace_search():
    mappings = json.loads((Path(__file__).parents[1] / 'configs/mcp.json').read_text())
    assert [name for name, mapping in mappings.items() if mapping.get('allow_unmetered')] == ['search_literature']
    assert mappings['search_literature']['cost_upper_cny'] is None


@pytest.mark.asyncio
async def test_hub_authorized_search_passes_unchanged_arguments():
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from arc.mcp_client import MCPHub, Capability, ServiceConfig
    seen = []
    class Result:
        is_error = False
        structured_content = {'papers': []}
        def model_dump(self, **kwargs): return {'content': []}
    class Client:
        async def call_tool(self, method, arguments, **kwargs):
            seen.append((method, arguments))
            return Result()
    @asynccontextmanager
    async def client(config): yield Client()
    hub = MCPHub([ServiceConfig('scholartrace', 'sse', url='https://example.org/sse')], {})
    hub._client = client
    hub.capabilities['search_literature'] = Capability('search_literature', 'scholartrace', 'query',
        {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']},
        'metadata', None, 'COST_UNOBSERVABLE', True)
    result = await hub.call('search_literature', {'query': 'precise full query'})
    assert seen == [('query', {'query': 'precise full query'})] and not result['is_error']


@pytest.mark.asyncio
async def test_interrupted_unmetered_action_is_not_repeated_and_does_not_block_resume(tmp_path):
    from arc.schemas import TaskRecord
    seen = []
    async def search(arguments, metadata):
        seen.append(arguments)
        return {}
    tool = BoundTool('search_literature', {'type': 'object', 'properties': {'query': {'type': 'string'}}},
        search, None, 'COST_UNOBSERVABLE', 'scholartrace', True, True)
    runtime, store, ledger, _ = setup_runtime(tmp_path, [], tools={'search_literature': tool})
    call = {'id': 'provider1', 'function': {'name': 'search_literature', 'arguments': '{"query":"test"}'}}
    record = TaskRecord(task_id='task_fixture', run_id='run_fixture',
        input_hash='test', prompt_hash='test', model_config_hash='test')
    ledger.register_unmetered('stage', 'interrupted', allow_unmetered=True, service='scholartrace',
        method='search_literature', task_id=record.task_id, run_id=record.run_id, tool_call_id='provider1',
        arguments={'query': 'test'}, parent_call_id='model1', raw_response_artifact_path='missing.raw.json')
    ledger.mark_started('interrupted')
    state = {'pending_tool': 'interrupted', 'tool_trace': [], 'messages': []}
    await runtime._execute_tool(record, state, call, ['search_literature'], 'model1')
    assert seen == [] and state['pending_tool'] is None
    assert state['tool_trace'][0]['outcome_status'] == 'unmetered_outcome_unknown'
    assert ledger.get_call('interrupted')['state'] == 'SETTLED'
    assert ledger.summary('parent')['unknown_calls'] == 0
    await runtime.close()


@pytest.mark.asyncio
async def test_unapproved_unknown_tool_still_stops_before_remote_action(tmp_path):
    from arc.runtime import RuntimePaused
    from arc.schemas import TaskRecord
    seen = []
    async def search(arguments, metadata): seen.append(arguments)
    tool = BoundTool('search_literature', {'type': 'object', 'properties': {}}, search,
        None, 'COST_UNOBSERVABLE', 'scholartrace')
    runtime, store, ledger, _ = setup_runtime(tmp_path, [], tools={'search_literature': tool})
    record = TaskRecord(task_id='task_fixture', run_id='run_fixture', input_hash='test', prompt_hash='test', model_config_hash='test')
    with pytest.raises(RuntimePaused, match='COST_UNOBSERVABLE'):
        await runtime._execute_tool(record, {}, {'id': 'p', 'function': {'name': 'search_literature', 'arguments': '{}'}},
            ['search_literature'], 'model1')
    assert seen == [] and ledger.list_calls() == []
    await runtime.close()


def test_report_explicitly_excludes_unmetered_costs(tmp_path, monkeypatch):
    from arc.reports import render_run
    from tests.test_discovery_workflow import fixture
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    ledger.register_unmetered(run.budget_account_id, 'unmetered-report', allow_unmetered=True,
        service='scholartrace', method='search_literature')
    ledger.mark_started('unmetered-report')
    ledger.finish_unmetered('unmetered-report')
    paths = render_run(store, run.run_id, tmp_path / 'report')
    text = paths['cost'].read_text()
    assert '外部费用未计量' in text and '不能视为总费用或总费用上界' in text
    assert 'unmetered' in text


@pytest.mark.asyncio
async def test_scholartrace_papers_without_public_identifier_remain_visible_not_fake_sources(tmp_path):
    from arc.runtime import build_tools
    from arc.mcp_client import Capability
    from arc.store import Store
    class Hub:
        capabilities = {'search_literature': Capability('search_literature', 'scholartrace', 'query',
            {'type': 'object', 'properties': {}}, 'metadata', None, 'COST_UNOBSERVABLE', True)}
        calls = 0
        async def call(self, name, arguments):
            self.calls += 1
            return {'is_error': False, 'structured_content': {'result': json.dumps({'status': 'success',
                'papers': [{'paper_id': 'provider:local-paper', 'title': 'Causal visual grounding',
                    'authors': ['A. Author'], 'year': 2026, 'abstract': 'A specific research abstract.'}]})}}
    store = Store(tmp_path / 'state.sqlite')
    hub = Hub()
    tool = build_tools(store, hub)['search_literature']
    metadata = {'raw_response_artifact_path': 'raw/literature.json'}
    result = await tool.handler({}, metadata)
    assert result['source_ids'] == [] and store.list_sources() == []
    candidate = result['unregistered_candidates'][0]
    assert candidate['title'] == 'Causal visual grounding' and candidate['paper_id'] == 'provider:local-paper'
    assert candidate['citation_eligible'] is False and candidate['identity_status'] == 'identity_unresolved'
    assert candidate['content_origin'] == 'metadata' and 'source_id' not in candidate
    assert await tool.handler({}, metadata) == result and hub.calls == 1
