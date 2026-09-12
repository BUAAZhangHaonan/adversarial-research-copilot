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


@pytest.mark.asyncio
async def test_explicit_new_writing_task_publishes_current_report(tmp_path, monkeypatch):
    from arc.discovery_workflow import finish_stage
    settings, run, store, ledger, field, seed, _ = fixture(tmp_path, monkeypatch)
    key='polish.after_candidate_recovery1'
    store.update_run(run.run_id, state={**run.state, 'field_brief':field, 'polish_task_key':key})
    text={'stage_summary':'Current stage is ready for human reading.', 'overview':'Uncertainty remains.',
          'candidates':[], 'cited_source_ids':[]}
    runtime=AccessRuntime({key:text})
    runtime.loader.manifest['prompts']['writer.POLISH']={'tools':[]}
    await finish_stage(WorkflowEngine(store,runtime,settings),run.run_id,'finished')
    final=store.get_run(run.run_id)
    assert final.state['polish']==text
    assert [k for k,_,_ in runtime.calls]==[key]
    assert final.state['task_inputs'][key]['payload']['candidates']==[]
