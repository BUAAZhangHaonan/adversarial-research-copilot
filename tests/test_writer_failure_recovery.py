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
async def test_writer_failure_does_not_discard_completed_research(tmp_path, monkeypatch):
    from arc.discovery_workflow import finish_stage
    settings, run, store, ledger, field, seed, _ = fixture(tmp_path, monkeypatch)
    store.update_run(run.run_id, state={**run.state, 'field_brief':field})
    runtime = AccessRuntime({'polish':RuntimePaused('PAUSED_PROTOCOL','INVALID_OUTPUT_AFTER_REPAIR')})
    runtime.loader.manifest['prompts']['writer.POLISH'] = {'tools':[]}
    engine = WorkflowEngine(store, runtime, settings)
    await finish_stage(engine, run.run_id, 'finished')
    final = store.get_run(run.run_id)
    assert final.status == 'COMPLETED' and final.state['polish_failure']['reason'] == 'INVALID_OUTPUT_AFTER_REPAIR'
    assert 'polish' not in final.state
