"""Access failures close locally; they never certify a blocked draft or stop other draws."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from arc.discovery_models import CandidateCheck, FieldBrief, SketchResult, TriageResult
from arc.evidence_continuation import validate_evidence_limit_result
from arc.runtime import RuntimePaused
from arc.workflows import WorkflowEngine
from tests.test_discovery_workflow import ScriptedRuntime, fixture, sketch, triage, checked


class AccessRuntime(ScriptedRuntime):
    async def invoke(self, **kwargs):
        key = kwargs['task_id'].split('.', 1)[1]
        value = self.results[key]
        if isinstance(value, RuntimePaused):
            self.calls.append((key, kwargs['role'], kwargs['task']))
            self.payloads[key] = deepcopy(kwargs['payload'])
            self.profiles[key] = list(kwargs['tool_profile'])
            raise value
        envelope = await super().invoke(**kwargs)
        if key in getattr(self, 'blocked', set()):
            return SimpleNamespace(result=envelope.result, result_status='needs_evidence',
                capability_requests=[], evidence_requests=[], note='Cannot retrieve the critical paper.')
        validate_evidence_limit_result(envelope, kwargs['payload'])
        return envelope


@pytest.mark.asyncio
@pytest.mark.parametrize('original_reason', ['critical_source_unavailable', 'SOURCE_READ_NO_PROGRESS', 'TOOL_REMOTE_RESULT_UNKNOWN'])
async def test_missing_literature_keeps_original_failure_and_finishes_remaining_draws(tmp_path, monkeypatch, original_reason):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=2)
    check = checked(seed, brief['source_notes'][0])
    limited = deepcopy(check)
    limited['note'].update(decision='lead', reason='A potentially useful question; the nearest paper remains unread.')
    results = {'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('investigate'),
        'idea1.check': RuntimePaused('PAUSED_EXTERNAL', original_reason),
        'idea1.check.with_available_evidence': limited,
        'idea2.sketch': sketch(seed), 'idea2.triage': triage('drop')}
    runtime = AccessRuntime(results)
    runtime.tools['request_capability'] = object()
    engine = WorkflowEngine(store, runtime, settings)
    final = await engine.execute(run.run_id)
    assert final.status == 'COMPLETED'
    assert final.stop_reason == 'finished_with_evidence_limits_human_decision'
    ideas = store.list_discovery_ideas(run.run_id)
    assert len(ideas) == 2 and ideas[0]['note']['decision'] == 'lead' and ideas[1]['status'] == 'drop'
    assert runtime.profiles['idea1.check.with_available_evidence'] == []
    entry = final.state['evidence_limits']['idea1.check']
    assert entry['status'] == 'limited' and entry['source_task_id'] == run.run_id + '.idea1.check'
    assert final.state['idea1.check_trace_tasks'] == [run.run_id + '.idea1.check', run.run_id + '.idea1.check.with_available_evidence']
    before = len(runtime.calls)
    # Resume uses the accepted local closure and never resends the failed retrieval task.
    from arc.discovery_workflow import discover
    await discover(engine, run.run_id)
    assert len(runtime.calls) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('closure_reason,status', [('critical_source_unavailable','PAUSED_EXTERNAL'), ('INVALID_OUTPUT_AFTER_REPAIR','PAUSED_PROTOCOL')])
async def test_even_failed_closure_parks_one_candidate_without_research_acceptance(tmp_path, monkeypatch, closure_reason, status):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=2)
    runtime = AccessRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('investigate'),
        'idea1.check': RuntimePaused('PAUSED_EXTERNAL', 'SOURCE_READ_NO_PROGRESS'),
        'idea1.check.with_available_evidence': RuntimePaused(status, closure_reason),
        'idea2.sketch': sketch(seed), 'idea2.triage': triage('park')})
    final = await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    first, second = store.list_discovery_ideas(run.run_id)
    assert final.status == 'COMPLETED' and second['status'] == 'park'
    assert first['status'] == 'evidence_limited' and first['note'] is None
    assert 'idea1.check' not in final.state
    assert final.state['evidence_limits']['idea1.check']['status'] == 'parked'


@pytest.mark.asyncio
async def test_entire_survey_unavailable_is_reported_without_invented_field_judgment(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch, draws=2)
    runtime = AccessRuntime({'survey': RuntimePaused('PAUSED_EXTERNAL', 'SOURCE_READ_NO_PROGRESS'),
        'survey.with_available_evidence': RuntimePaused('PAUSED_EXTERNAL', 'critical_source_unavailable'),
        'idea1.sketch': sketch(action='skip'), 'idea2.sketch': sketch(action='skip')})
    final = await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert final.status == 'COMPLETED'
    assert final.state['field_brief']['source_notes'] == []
    assert final.state['field_brief']['research_lines'] == []
    assert final.state['field_brief']['search_limits']
    assert len(store.list_discovery_ideas(run.run_id)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('reason,status', [('REMOTE_RESULT_UNKNOWN','UNKNOWN'), ('BUDGET_EXHAUSTED','PAUSED_BUDGET'), ('INVALID_PROVIDER_USAGE','PAUSED_PROTOCOL'),
    ('DEPENDENCY_ENVIRONMENT_CHANGED_FORK_REQUIRED','PAUSED_PROTOCOL')])
@pytest.mark.parametrize('at_closure', [False, True])
async def test_model_and_budget_failures_are_not_silently_bypassed(tmp_path, monkeypatch, reason, status, at_closure):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    results = {'survey': RuntimePaused(status, reason)}
    if at_closure:
        results = {'survey': RuntimePaused('PAUSED_EXTERNAL', 'SOURCE_READ_NO_PROGRESS'),
            'survey.with_available_evidence': RuntimePaused(status, reason)}
    runtime = AccessRuntime(results)
    with pytest.raises(RuntimePaused) as error:
        await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert error.value.status == status and error.value.reason == reason
    assert not store.list_discovery_ideas(run.run_id)


@pytest.mark.asyncio
async def test_pending_valid_draft_is_not_accepted_as_discuss(tmp_path, monkeypatch):
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    runtime = AccessRuntime({'survey': brief, 'idea1.sketch': sketch(seed), 'idea1.triage': triage('investigate'),
        'idea1.check': checked(seed, brief['source_notes'][0]),
        'idea1.check.with_available_evidence': RuntimePaused('PAUSED_EXTERNAL','critical_source_unavailable')})
    runtime.blocked = {'idea1.check'}
    final = await WorkflowEngine(store, runtime, settings).execute(run.run_id)
    assert final.status == 'COMPLETED'
    assert store.list_discovery_ideas(run.run_id)[0]['note'] is None


def test_completion_contract_rejects_unsupported_promotion():
    brief = FieldBrief(overview='Limited materials', research_lines=[], openings=[], source_notes=[], search_limits=[])
    with pytest.raises(ValueError, match='SURVEY_REQUIRES'):
        validate_evidence_limit_result(SimpleNamespace(result_status='complete', result=brief), {'evidence_limit_handoff': True})
    value = TriageResult.model_validate(triage('investigate'))
    with pytest.raises(ValueError, match='TRIAGE_REQUIRES'):
        validate_evidence_limit_result(SimpleNamespace(result_status='complete', result=value), {'evidence_limit_handoff': True})
    with pytest.raises(ValueError, match='NOT_THE_BATCH'):
        validate_evidence_limit_result(SimpleNamespace(result_status='complete', result=SketchResult.model_validate(sketch(action='stop'))), {'evidence_limit_handoff': True})


@pytest.mark.asyncio
async def test_newly_retrieved_source_ids_survive_handoff_and_interrupted_closure(tmp_path, monkeypatch):
    from arc.schemas import SourceRecord
    from arc.runtime import reference_ids, SOURCE_REF_KEYS
    from arc.evidence_continuation import call_with_evidence_limits
    settings, run, store, ledger, brief, seed, _ = fixture(tmp_path, monkeypatch)
    source = store.register_source(SourceRecord(title='New paper', url='https://example.org/new',
        source_type='paper', access_status='retrieved', content_origin='original'), content='New actual passage.')
    limited = checked(seed, brief['source_notes'][0]); limited['note']['decision'] = 'lead'
    runtime = AccessRuntime({'check': RuntimePaused('PAUSED_EXTERNAL','SOURCE_READ_NO_PROGRESS'),
        'check.with_available_evidence': limited})
    runtime.traces['check'] = [{'name':'read_paper','status':'completed', 'source_ids':[source.source_id],
        'result': {'is_error':False,'source_id':source.source_id,'content':'New actual passage.'}}]
    runtime.before.add('check.with_available_evidence')
    engine=WorkflowEngine(store,runtime,settings)
    with pytest.raises(InterruptedError):
        await call_with_evidence_limits(engine,run.run_id,'check','scout','CHECK',payload={'seed':seed})
    await call_with_evidence_limits(engine,run.run_id,'check','scout','CHECK',payload={'seed':seed,'changed':'must not replace frozen input'})
    payload=runtime.payloads['check.with_available_evidence']
    assert source.source_id in reference_ids(payload,SOURCE_REF_KEYS)
    assert 'changed' not in payload
    assert sum(key=='check' for key,_,_ in runtime.calls)==1


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['develop','run'])
async def test_failed_prestudy_closure_finishes_as_limited_without_old_discuss(tmp_path,monkeypatch,mode):
    from arc.cli import new_run
    settings,origin,store,ledger,brief,seed,_=fixture(tmp_path,monkeypatch)
    store.update_run(origin.run_id,state={**origin.state,'field_brief':brief})
    idea=store.save_discovery_idea(origin.run_id,'idea1',seed=seed,
        note=checked(seed,brief['source_notes'][0])['note'],status='checked')
    run=new_run(settings,mode,idea_id=idea['idea_id'])
    runtime=AccessRuntime({'prestudy':RuntimePaused('PAUSED_EXTERNAL','SOURCE_READ_NO_PROGRESS'),
        'prestudy.with_available_evidence':RuntimePaused('PAUSED_PROTOCOL','INVALID_OUTPUT_AFTER_REPAIR')})
    final=await WorkflowEngine(store,runtime,settings).execute(run.run_id)
    assert final.status=='COMPLETED' and final.state['prestudy_evidence_limited'] is True
    assert not final.state.get('prestudy_note')
    assert store.list_discovery_ideas(origin.run_id)[0]['note']['decision']=='discuss'


@pytest.mark.asyncio
async def test_already_received_blocked_draft_closes_without_replaying_old_tool_profile(tmp_path,monkeypatch):
    import json
    from arc.schemas import TaskRecord
    from arc.evidence_continuation import call_with_evidence_limits
    settings,run,store,ledger,brief,seed,_=fixture(tmp_path,monkeypatch)
    old=checked(seed,brief['source_notes'][0])
    limited=deepcopy(old); limited['note']['decision']='lead'
    path=f'runs/{run.run_id}/blocked-replay.json'
    store.save_artifact(path,json.dumps({'response':{'message':{'content':json.dumps({
        'result_status':'needs_evidence','result':old})}}}))
    store.put_task(TaskRecord(task_id=run.run_id+'.check',run_id=run.run_id,status='PAUSED_EXTERNAL',
        input_hash='fixture',prompt_hash='fixture',model_config_hash='fixture',response_artifact_path=path))
    runtime=AccessRuntime({'check.with_available_evidence':limited})
    result=await call_with_evidence_limits(WorkflowEngine(store,runtime,settings),run.run_id,
        'check','scout','CHECK',payload={'seed':seed})
    assert result.note.decision=='lead'
    assert [key for key,_,_ in runtime.calls]==['check.with_available_evidence']
    assert store.get_task(run.run_id+'.check').accepted_result is None
