"""Workflow gates use real adapter return shapes, not model claims of reading."""
from decimal import Decimal

import pytest

from arc.config import Settings
from arc.mcp_client import Capability
from arc.runtime import build_tools
from arc.workflows import WorkflowEngine, WorkflowPause
from tests.test_selection import research_draft, research_store
from tests.test_workflows import ScriptedRuntime, campaign_run


async def external_trace(store, run_id, name, case):
    """A local fake service returns text; the production adapter registers it."""
    text = 'A retrieved original reports a controlled comparison. ' * 300
    arguments = {'query': 'controlled comparison'}
    if name == 'read_web':
        arguments = {'url': 'https://example.org/evidence-gate', 'max_chars': 14000}
        if case == 'empty_body':
            returned = ''
        elif case == 'cached_body':
            returned = text[:14000] + f'\n...[truncated {len(text)} chars]'
        else:
            returned = text[:1000]
        body = {'title': None if case == 'empty_sources' else 'Original fixture',
                'url': arguments['url'], 'text': returned, 'extractor': 'fixture',
                'resource': {'content_hash': 'fixture-document'}}
    elif name == 'read_paper':
        body = {'status': 'success',
                'paper': {} if case == 'empty_sources' else {
                    'title': 'Original fixture', 'arxiv_id': '2401.00001v1'},
                'markdown': '' if case == 'empty_body' else (
                    text if case == 'cached_body' else text[:1000])}
    else:
        body = {'papers' if name == 'search_literature' else 'results': []}
    calls = []

    class Hub:
        capabilities = {name: Capability(name, 'fixture', name, {},
            'metadata' if name.startswith('search_') else 'original', Decimal(0), 'OFFLINE_FIXTURE')}

        async def call(self, operation, args):
            calls.append((operation, args))
            return {'is_error': case == 'service_error', 'structured_content': body, 'content': []}

    result = await build_tools(store, Hub())[name].handler(arguments, {
        'run_id': run_id, 'raw_response_artifact_path': 'tests/evidence-gate.raw.json'})
    assert calls == [(name, arguments)]
    # Include completed+is_error to ensure a status label alone cannot pass.
    return [{'call_id': 'tool_fixture', 'name': name, 'status': 'completed',
             'arguments': arguments, 'source_ids': result.get('source_ids', []), 'result': result}]


async def execute_with_trace(store, run, stage, trace):
    key = '.fresh_verification' if stage == 'develop' else '.draw1.novelty'

    class CheckRuntime(ScriptedRuntime):
        def tool_trace(self, task_id):
            return trace if task_id.endswith(key) else super().tool_trace(task_id)

    runtime = CheckRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    result = await engine.execute(run.run_id)
    return engine, runtime, result


def gate_run(store, stage):
    if stage == 'develop':
        card = store.save_card(research_draft())
        return store.create_run('develop', card_id=card.card_id, card_version=card.version)
    return campaign_run(store, max_draws=1)[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['develop', 'novelty'])
@pytest.mark.parametrize('operation', ['read_web', 'read_paper'])
@pytest.mark.parametrize('case', ['empty_sources', 'empty_body', 'service_error'])
async def test_empty_external_reads_do_not_satisfy_verification_or_replay(tmp_path, stage, operation, case):
    store, _, _ = research_store(tmp_path)
    run = gate_run(store, stage)
    trace = await external_trace(store, run.run_id, operation, case)
    engine, runtime, result = await execute_with_trace(store, run, stage, trace)
    assert result.status == 'PAUSED_EXTERNAL'
    assert result.stop_reason == ('fresh_verification_not_executed' if stage == 'develop'
                                  else 'closest_work_check_not_executed')
    downstream = 'developer' if stage == 'develop' else 'selector'
    assert not any(call['role'] == downstream for call in runtime.calls)
    before = len(runtime.calls)
    resumed = await engine.execute(run.run_id)
    assert resumed.status == 'PAUSED_EXTERNAL'
    assert len(runtime.calls) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['develop', 'novelty'])
@pytest.mark.parametrize('operation', ['read_web', 'read_paper'])
@pytest.mark.parametrize('case', ['inline_body', 'cached_body'])
async def test_actual_registered_text_with_coverage_satisfies_verification(tmp_path, stage, operation, case):
    store, _, _ = research_store(tmp_path)
    run = gate_run(store, stage)
    trace = await external_trace(store, run.run_id, operation, case)
    coverage = trace[0]['result']['sources'][0]
    assert coverage['content_chars'] > 0
    assert store.get_record(coverage['source_id'])['content']
    if case == 'cached_body':
        assert coverage['content'] is None  # Retrieved text lives in the registry.
    _, runtime, result = await execute_with_trace(store, run, stage, trace)
    assert result.status == 'COMPLETED'
    downstream = 'developer' if stage == 'develop' else 'selector'
    assert any(call['role'] == downstream for call in runtime.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['develop', 'novelty'])
@pytest.mark.parametrize('operation', ['search_web', 'search_literature'])
async def test_successful_zero_result_search_counts_as_search_not_original_read(tmp_path, stage, operation):
    store, _, _ = research_store(tmp_path)
    run = gate_run(store, stage)
    trace = await external_trace(store, run.run_id, operation, 'zero_results')
    assert trace[0]['result']['source_ids'] == [] and trace[0]['result']['sources'] == []
    engine, _, result = await execute_with_trace(store, run, stage, trace)
    assert result.status == 'COMPLETED'
    assert len(store.list_sources()) == 1  # Only the existing synthetic material.
    # A search does not discharge a request to actually reread a target original.
    with pytest.raises(WorkflowPause, match='source_recheck_original_not_read'):
        engine._validate_source_recheck({'target_source_ids': ['src_synthetic'],
            'replacement_task_id': run.run_id + ('.fresh_verification' if stage == 'develop' else '.draw1.novelty')})


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', ['missing_coverage', 'unregistered_source', 'metadata', 'wrong_inline', 'failed_trace'])
async def test_read_label_and_source_id_do_not_replace_actual_body_coverage(tmp_path, invalid):
    store, _, _ = research_store(tmp_path)
    run = gate_run(store, 'develop')
    trace = await external_trace(store, run.run_id, 'read_web', 'inline_body')
    coverage = trace[0]['result']['sources'][0]
    if invalid == 'missing_coverage':
        coverage.pop('content_chars')
    elif invalid == 'unregistered_source':
        coverage['source_id'] = 'src_unknown'
        trace[0]['source_ids'] = trace[0]['result']['source_ids'] = ['src_unknown']
    elif invalid == 'metadata':
        from arc.schemas import SourceRecord
        source = store.register_source(SourceRecord(title='Search metadata', url='https://example.org/metadata',
            source_type='paper', access_status='metadata_only', content_origin='metadata'))
        coverage['source_id'] = source.source_id
        trace[0]['source_ids'] = trace[0]['result']['source_ids'] = [source.source_id]
    elif invalid == 'wrong_inline':
        coverage['content'] = 'This was not the retrieved passage.'
    else:
        trace[0]['status'] = 'error'
    _, _, result = await execute_with_trace(store, run, 'develop', trace)
    assert result.status == 'PAUSED_EXTERNAL'
    assert result.stop_reason == 'fresh_verification_not_executed'
