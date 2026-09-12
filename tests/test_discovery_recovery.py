"""Regression cases from the Arena survey failure; no paid calls."""
from copy import deepcopy
import json
import pytest
from arc.discovery_validation import validate_source_access, repair_source_catalog
from arc.discovery_models import FieldBrief
from arc.runtime import RuntimePaused
from arc.workflows import WorkflowEngine
from arc.schemas import SourceRecord
from tests.test_discovery_validation import source_store, brief
from tests.test_discovery_workflow import fixture, sketch, triage, checked
from tests.test_evidence_continuation import AccessRuntime

@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['INVALID_OUTPUT_AFTER_REPAIR',
    'TOOL_ARGUMENTS_INVALID_AFTER_CORRECTION', 'TOOL_CORRECTION_CALLS_MISMATCH',
    'TOOL_CORRECTION_REQUIRED'])
async def test_bad_output_closes_once_then_remaining_draw_continues(tmp_path, monkeypatch, failure):
    settings, run, store, ledger, field, seed, _ = fixture(tmp_path, monkeypatch, draws=2)
    runtime = AccessRuntime({'survey':field, 'idea1.sketch':sketch(seed), 'idea1.triage':triage('investigate'),
        'idea1.check':RuntimePaused('PAUSED_PROTOCOL',failure),
        'idea1.check.with_available_evidence':RuntimePaused('PAUSED_PROTOCOL','INVALID_OUTPUT_AFTER_REPAIR'),
        'idea2.sketch':sketch(seed), 'idea2.triage':triage('park')})
    final = await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert final.status == 'COMPLETED'
    first, second = store.list_discovery_ideas(run.run_id)
    assert first['note'] is None and second['status'] == 'park'
    entry = final.state['evidence_limits']['idea1.check']
    assert entry['status'] == 'parked' and '校验' in entry['reason']
    assert len([c for c in runtime.calls if c[0].startswith('idea1.check')]) == 2


def test_runtime_failure_follows_explicit_revision_even_without_pending_task():
    from types import SimpleNamespace
    from arc.evidence_continuation import _source_key
    run = SimpleNamespace(state={'pending_task':None, 'task_retries':{'survey':[
        {'replacement_key':'survey.protocol_retry1'}]}})
    assert _source_key(run, 'survey') == 'survey.protocol_retry1'


