"""Compact search diagnostics preserve usable hits and durable remote-response reuse."""
import json
from decimal import Decimal

import pytest

from arc.mcp_client import Capability
from arc.runtime import build_tools, compact_search_diagnostics
from arc.store import Store


@pytest.mark.asyncio
async def test_partial_engine_failure_keeps_hits_and_compact_query_diagnostics(tmp_path):
    query = 'visual hallucination controlled prior synthetic training'
    detail = "HTTPStatusError: Client error '403 Forbidden' for url 'https://engine.invalid/search?q=" + query.replace(' ', '+') + "'\nFor more information check: https://error.invalid/help\nTraceback private stack"
    body = {'query': query, 'variants': [query, '"' + query + '"'], 'count': 1,
        'engine_errors': {'mojeek': detail, 'searxng': 'ReadTimeout: timed out'}, 'spam_filtered': 5,
        'spam_examples': ['A very long irrelevant title' * 100],
        'results': [{'title': 'Relevant paper', 'url': 'https://example.org/paper', 'snippet': 'Useful abstract.'}]}
    calls = []
    class Hub:
        capabilities = {'search_web': Capability('search_web', 'webresearch', 'web_search', {}, 'metadata', Decimal(0), 'OFFLINE_FIXTURE')}
        async def call(self, name, arguments):
            calls.append((name, arguments))
            return {'is_error': False, 'structured_content': {'result': json.dumps(body)}, 'content': []}
    store = Store(tmp_path / 'state.sqlite')
    tool = build_tools(store, Hub())['search_web']
    args = {'query': query, 'max_results': 8}
    metadata = {'run_id': 'fixture', 'raw_response_artifact_path': 'tools/search.raw.json'}
    result = await tool.handler(args, metadata)
    assert not result['is_error'] and result['sources'][0]['title'] == 'Relevant paper'
    assert len(result['source_ids']) == 1 and result['raw_artifact_path'] == metadata['raw_response_artifact_path']
    diagnostic = result['search_diagnostics']
    assert diagnostic['query'] == query and diagnostic['query_matches_input']
    assert diagnostic['variants'] == ['"' + query + '"']
    assert diagnostic['degraded'] and diagnostic['spam_filtered'] == 5
    assert '403 Forbidden' in diagnostic['engine_errors']['mojeek']
    assert 'ReadTimeout' in diagnostic['engine_errors']['searxng']
    assert 'https://' not in diagnostic['engine_errors']['mojeek'] and '\n' not in diagnostic['engine_errors']['mojeek']
    assert 'Traceback' not in json.dumps(diagnostic) and 'spam_examples' not in diagnostic
    raw = json.loads(store.read_artifact(metadata['raw_response_artifact_path']))
    assert json.loads(raw['structured_content']['result'])['engine_errors']['mojeek'] == detail
    again = await tool.handler(args, metadata)
    assert again == result and len(calls) == 1  # No implicit remote retry.


def test_clean_or_empty_search_is_not_marked_failed_by_diagnostics():
    result = compact_search_diagnostics({'query': 'q', 'variants': ['q'], 'engine_errors': {}, 'count': 0}, {'query': 'q'})
    assert result == {'query': 'q', 'query_matches_input': True, 'variants': [],
                      'engine_errors': {}, 'degraded': False, 'count': 0}


def test_large_diagnostics_are_bounded_and_compaction_is_explicit():
    result = compact_search_diagnostics({'query': 'q' * 900,
        'variants': ['v' * 900 + str(i) for i in range(8)],
        'engine_errors': {str(i): 'RuntimeError: ' + 'x' * 2000 for i in range(12)}}, {'query': 'other'})
    assert len(result['query']) == 512 and result['query_truncated']
    assert not result['query_matches_input']
    assert len(result['variants']) == 3 and result['variants_compacted']
    assert len(result['engine_errors']) == 8 and result['engine_errors_omitted'] == 4
    assert all(len(value) <= 192 for value in result['engine_errors'].values())


def test_unavailable_optional_fields_do_not_create_false_diagnostics():
    assert compact_search_diagnostics({'query': None, 'variants': None, 'engine_errors': None}, {}) == {}
