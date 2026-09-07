import pytest
from arc.config import Settings
from arc.workflows import WorkflowEngine
from tests.test_selection import research_store
from tests.test_workflows import ScriptedRuntime, campaign_run

@pytest.mark.asyncio
@pytest.mark.parametrize('recheck_fails', [False, True])
async def test_invalid_quote_has_one_separate_source_task_and_preserves_rejection(tmp_path, recheck_fails):
    import json
    from arc.runtime import RuntimePaused
    from arc.schemas import TaskRecord
    store, _, _ = research_store(tmp_path)
    _, run = campaign_run(store, max_draws=1)
    class QuoteRuntime(ScriptedRuntime):
        async def invoke(self, **kw):
            if kw['task_id'].endswith('.shared'):
                result = self.reply('investigator', 'INVOKE', kw['payload'], kw['task_id'])
                path = self.store.save_artifact('tests/rejected.json', json.dumps({
                    'response': {'message': {'content': json.dumps({'result': result})}}}))
                self.store.put_task(TaskRecord(task_id=kw['task_id'], run_id=run.run_id,
                    input_hash='frozen', prompt_hash='frozen', model_config_hash='frozen',
                    status='PAUSED_PROTOCOL', error='excerpt_not_in_returned_source',
                    response_artifact_path=path))
                raise RuntimePaused('PAUSED_PROTOCOL', 'excerpt_not_in_returned_source')
            assert kw['task_id'].endswith('.source_recheck')
            assert kw['tool_profile'] == ['read_record', 'request_capability']
            assert kw['payload']['sources_from_rejected_task'][0]['source_id'] == 'src_synthetic'
            if recheck_fails:
                self.calls.append({'task_id': kw['task_id']})
                raise RuntimePaused('PAUSED_PROTOCOL', 'excerpt_not_in_returned_source')
            return await super().invoke(**kw)
        def reply(self, role, task, payload, task_id):
            result = super().reply(role, task, payload, task_id)
            if task_id.endswith('.source_recheck'):
                result['findings'] = [{'claim': 'The variables were not isolated.',
                    'conditions': ['synthetic'], 'source_id': 'src_synthetic',
                    'locator': None, 'locator_status': 'locator_unverified', 'relation': 'limits',
                    'origin': 'original', 'excerpt': 'they do not isolate the variables.',
                    'support_explanation': 'The authors explicitly state the limitation.'}]
            return result
        def tool_trace(self, task_id):
            if task_id.endswith('.source_recheck'):
                return [{'name':'read_record', 'status':'completed', 'source_ids':['src_synthetic']}]
            return super().tool_trace(task_id)
    runtime = QuoteRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings())
    if recheck_fails:
        with pytest.raises(RuntimePaused, match='excerpt_not_in_returned_source'):
            await engine.investigate(run.run_id, 'shared', ['Check the confound.'], fresh=True)
        assert len(runtime.calls) == 1
        assert store.list_evidence(run_id=run.run_id) == []
    else:
        await engine.investigate(run.run_id, 'shared', ['Check the confound.'], fresh=True)
        before = len(runtime.calls)
        await engine.investigate(run.run_id, 'shared', ['Check the confound.'], fresh=True)
        assert len(runtime.calls) == before
        assert len(store.list_evidence(run_id=run.run_id)) == 1
        assert store.get_run(run.run_id).state['shared_trace_tasks'] == [
            run.run_id + '.shared', run.run_id + '.shared.source_recheck']
    rejected = store.get_task(run.run_id + '.shared')
    assert rejected.status == 'PAUSED_PROTOCOL' and rejected.accepted_result is None

@pytest.mark.asyncio
async def test_cross_record_invalid_selection_pauses_without_acceptance_or_paid_replay(tmp_path):
    store, _, _ = research_store(tmp_path)
    _, run = campaign_run(store, max_draws=1)
    class InvalidSelection(ScriptedRuntime):
        def reply(self, role, task, payload, task_id):
            result = super().reply(role, task, payload, task_id)
            if role == 'selector':
                result['selection_checks']['test_identifiability']['status'] = 'unknown'
            return result
    runtime = InvalidSelection(store)
    engine = WorkflowEngine(store, runtime, Settings())
    result = await engine.execute(run.run_id)
    assert result.status == 'PAUSED_PROTOCOL'
    assert result.stop_reason == 'MAIN_REPORT_PREREQUISITE_UNESTABLISHED'
    assert not any(c.selection == 'MAIN_REPORT' for c in store.list_cards(run_id=run.run_id))
    prior_calls = len(runtime.calls)
    resumed = await engine.execute(run.run_id)
    assert resumed.status == 'PAUSED_PROTOCOL'
    assert len(runtime.calls) == prior_calls

@pytest.mark.asyncio
async def test_novelty_requested_evidence_trace_is_kept_through_continuation(tmp_path):
    from arc.schemas import Envelope
    store, _, _ = research_store(tmp_path)
    _, run = campaign_run(store, max_draws=1)
    class EvidenceContinuation(ScriptedRuntime):
        def tool_trace(self, task_id):
            if '.novelty' in task_id and '.requested_evidence' not in task_id:
                return []
            return super().tool_trace(task_id)
        async def invoke(self, **kw):
            if kw['role'] == 'novelty_examiner' and '.after_evidence' not in kw['task_id']:
                return Envelope[kw['result_schema']](schema_version='arc.v1',task_id=kw['task_id'],
                    subject=kw['subject'],result_status='needs_evidence',result=None,
                    evidence_requests=[{'request_local_id':'r1','claim_id':None,'issue_id':None,
                        'draw_id':kw['subject'].campaign_id + '.draw1','question':'Does the original isolate both factors?',
                        'target_source_ids':['src_synthetic'],'queries':[],
                        'purpose':'Check the closest contribution',
                        'decision_if_supported':'Record coverage','decision_if_contradicted':'Assess remaining delta'}],
                    capability_requests=[],note='Need an original read.')
            return await super().invoke(**kw)
    runtime = EvidenceContinuation(store)
    result = await WorkflowEngine(store, runtime, Settings()).execute(run.run_id)
    assert result.status == 'COMPLETED'
    assert '.requested_evidence' in ''.join(result.state['draw1.novelty_trace_tasks'])
    assert len(store.list_cards(run_id=run.run_id)) == 1

@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['REASON', 'RETRIEVE', 'STOP'])
async def test_round_limit_and_resume_cover_each_control_branch(tmp_path, action):
    from arc.schemas import Claim
    from tests.test_selection import research_draft
    store, _, _ = research_store(tmp_path)
    draft = research_draft()
    draft.claims = [Claim(claim_id='claim_test', version=1, text='The two interventions can be distinguished.',
                         conditions=['synthetic factorial task'], kind='hypothesis', evidence_ids=[])]
    card = store.save_card(draft)
    run = store.create_run('run', card_id=card.card_id, card_version=card.version)
    class ActionRuntime(ScriptedRuntime):
        def reply(self, role, task, payload, task_id):
            result = super().reply(role, task, payload, task_id)
            if role == 'moderator':
                status = 'needs_retrieval' if action == 'RETRIEVE' else 'open'
                result.update(assessment='NEEDS_EVIDENCE', next_action=action,
                    stop_reason='evidence_action_exhausted' if action == 'STOP' else None,
                    updated_issues=[{'issue_id':'issue_test','claim_id':'claim_test','claim_version':1,
                        'content':'Check whether the design fixes total token count.', 'status':status,
                        'evidence_ids':[], 'resolution_criterion':'Inspect the original design for a fixed-budget condition.',
                        'change_this_round':'A concrete budget confound needs checking.',
                        'next_action':action, 'claim_kind':'hypothesis'}],
                    issue_transitions=[{'issue_id':'issue_test','from_status':None,'to_status':status,
                        'change_this_round':'Opened the budget-confound question.', 'basis_evidence_ids':[],
                        'basis_argument':'Uncontrolled tokens could mimic distance.', 'resolution_reason':None}])
            return result
    runtime = ActionRuntime(store)
    engine = WorkflowEngine(store, runtime, Settings(max_rounds=1))
    first = await engine.execute(run.run_id)
    assert first.status == 'COMPLETED' and first.state['rounds_completed'] == 1
    assert first.stop_reason == ('evidence_action_exhausted' if action == 'STOP' else 'max_rounds_reached')
    assert len([c for c in runtime.calls if c['role'] == 'moderator']) == 1
    assert len([c for c in runtime.calls if c['role'] == 'investigator']) == (action == 'RETRIEVE')
    before = len(runtime.calls)
    await engine.execute(run.run_id)
    assert len(runtime.calls) == before
