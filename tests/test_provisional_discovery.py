"""Unknown novelty belongs to CHECK, not a failed SKETCH/TRIAGE."""
from types import SimpleNamespace
import pytest
from arc.workflows import WorkflowEngine
from tests.test_discovery_workflow import fixture, sketch, triage, checked
from tests.test_evidence_continuation import AccessRuntime


class QuestionRuntime(AccessRuntime):
    async def invoke(self, **kwargs):
        result = await super().invoke(**kwargs)
        key = kwargs['task_id'].split('.', 1)[1]
        if key in self.blocked:
            result.evidence_requests = [{'question':'Unresolved novelty for '+key}]
        return result


@pytest.mark.asyncio
async def test_seed_and_investigate_decision_handoff_unknowns_without_paid_closure(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    runtime = QuestionRuntime({'survey':brief,'idea1.sketch':sketch(seed),
        'idea1.triage':triage('investigate'),'idea1.check':checked(seed,brief['source_notes'][0])})
    runtime.blocked={'idea1.sketch','idea1.triage'}
    final=await WorkflowEngine(store,runtime,settings).execute(run.run_id)
    assert final.status=='COMPLETED'
    assert [k for k,_,_ in runtime.calls]==['survey','idea1.sketch','idea1.triage','idea1.check']
    assert len(store.list_discovery_ideas(run.run_id))==1
    assert final.state['idea1.sketch_provisional']['research_verified'] is False
    assert final.state['idea1.triage_provisional']['result_status']=='needs_evidence'
    assert len(runtime.payloads['idea1.triage']['candidate_evidence_requests'])==1
    assert len(runtime.payloads['idea1.check']['candidate_evidence_requests'])==2
    assert 'evidence_limits' not in final.state


@pytest.mark.asyncio
async def test_final_check_still_cannot_promote_unverified_discuss(tmp_path, monkeypatch):
    from arc.runtime import RuntimePaused
    settings,run,store,ledger,brief,seed,_=fixture(tmp_path,monkeypatch)
    runtime=QuestionRuntime({'survey':brief,'idea1.sketch':sketch(seed),
        'idea1.triage':triage('investigate'),'idea1.check':checked(seed,brief['source_notes'][0]),
        'idea1.check.with_available_evidence':RuntimePaused('PAUSED_EXTERNAL','critical_source_unavailable')})
    runtime.blocked={'idea1.check'}
    final=await WorkflowEngine(store,runtime,settings).execute(run.run_id)
    assert final.status=='COMPLETED'
    idea=store.list_discovery_ideas(run.run_id)[0]
    assert idea['note'] is None and idea['status']=='evidence_limited'
    assert 'idea1.check_provisional' not in final.state


@pytest.mark.asyncio
async def test_saved_unverified_seed_reenters_validation_without_closure(tmp_path, monkeypatch):
    import json
    from arc.schemas import TaskRecord
    settings,run,store,ledger,brief,seed,_=fixture(tmp_path,monkeypatch)
    store.update_run(run.run_id,state={**run.state,'field_brief':brief})
    path=f'runs/{run.run_id}/saved-seed.json'
    store.save_artifact(path,json.dumps({'response':{'message':{'content':json.dumps({
        'result_status':'needs_evidence','result':sketch(seed)})}}}))
    store.put_task(TaskRecord(task_id=run.run_id+'.idea1.sketch',run_id=run.run_id,
        status='PAUSED_EXTERNAL',input_hash='fixture',prompt_hash='fixture',model_config_hash='fixture',
        response_artifact_path=path))
    runtime=QuestionRuntime({'idea1.sketch':sketch(seed),'idea1.triage':triage('park')})
    runtime.blocked={'idea1.sketch'}
    final=await WorkflowEngine(store,runtime,settings).execute(run.run_id)
    assert final.status=='COMPLETED'
    assert [k for k,_,_ in runtime.calls]==['idea1.sketch','idea1.triage']
    assert store.get_task(run.run_id+'.idea1.sketch').accepted_result is None
    assert store.list_discovery_ideas(run.run_id)[0]['seed']==seed
