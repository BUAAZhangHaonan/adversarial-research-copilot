"""Production 64000-character read limit and durable budget recovery."""
import json
import pytest
from arc.runtime import RuntimePaused
from tests.test_runtime import setup_runtime, invoke, sse, answer
from tests.test_tool_correction import tool_response, native, saved, restart


@pytest.mark.asyncio
async def test_64k_read_correction_budget_resume_preserves_source_and_output_config(tmp_path):
    from arc.runtime import build_tools
    from arc.schemas import SourceRecord
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses, amount='5.304')
    runtime.tools = build_tools(store)
    text = '中文🧪abc' * 20000
    source = store.register_source(SourceRecord(title='Unicode page fixture',
        url='https://example.org/long-paper', source_type='paper', access_status='retrieved',
        content_origin='original', content_complete=True, content_total_chars=len(text)), text)
    before = store.get_source(source.source_id).model_dump(mode='json')
    args = {'record_id': source.source_id, 'offset': 1000, 'limit': 64001}
    responses.extend([tool_response(native('oversized', args)),
        tool_response(native('corrected', {**args, 'limit': 64000})), sse(json.dumps(answer()))])
    with pytest.raises(RuntimePaused) as error:
        await invoke(runtime, tool_profile=['read_record'])
    assert error.value.status == 'PAUSED_BUDGET' and not runtime.tool_trace('task_fixture')
    assert saved(store)['tool_rejections'][0]['errors'][0]['expected'] == 64000
    ledger.add_budget('stage', '1', 'Offline fixture authorizes resumed read')
    resumed = restart(runtime)
    assert (await invoke(resumed, tool_profile=['read_record'])).result.value == 'valid'
    trace = resumed.tool_trace('task_fixture')
    assert len(trace) == 1 and trace[0]['result']['content'] == text[1000:65000]
    assert trace[0]['result']['content_offset'] == 1000
    assert trace[0]['result']['more_cached_content'] is True
    assert store.get_source(source.source_id).model_dump(mode='json') == before
    assert store.get_record(source.source_id)['content'] == text
    assert len(ledger.list_calls()) == 4 and ledger.summary('stage')['reserved_micro'] == 0
    assert all(r['max_tokens'] == 384000 and r['reasoning_effort'] == 'max' for r in requests)
    assert (await invoke(resumed, tool_profile=['read_record'])).result.value == 'valid'
    assert len(requests) == 3
    await runtime.close()
