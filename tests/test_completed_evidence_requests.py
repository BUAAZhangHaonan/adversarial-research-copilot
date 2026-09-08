"""Accepted moderator requests survive checkpoint aliases and reach retrieval."""
from __future__ import annotations

import pytest

from arc.config import Settings
from arc.retrying import prepare_task_retry
from arc.schemas import EvidenceRequest, Issue, IssueTransition
from arc.workflows import WorkflowEngine
from tests.test_selection import research_draft, research_store
from tests.test_task_retry import KEY, REASON, setup_case
from tests.test_workflows import ScriptedRuntime


def request(name):
    return EvidenceRequest(request_local_id=name, claim_id='claim_observation',
        issue_id='issue-coverage', draw_id=None, question=f'Check {name} coverage?',
        target_source_ids=['src_synthetic'], queries=[], purpose='Resolve coverage',
        decision_if_supported='Narrow the novelty claim',
        decision_if_contradicted='Retain the controlled intervention')


class RequestRuntime(ScriptedRuntime):
    def __init__(self, store, *, needs_evidence=False):
        super().__init__(store)
        self.needs_evidence = needs_evidence

    async def invoke(self, **kwargs):
        envelope = await super().invoke(**kwargs)
        if kwargs['role'] == 'moderator':
            key = kwargs['task_id']
            if self.needs_evidence and '.after_evidence' not in key:
                return envelope.model_copy(update={'result_status': 'needs_evidence', 'result': None,
                    'evidence_requests': [request('initial')]})
            name = 'reassessment' if '.evidence_reassessment' in key else 'final'
            return envelope.model_copy(update={
                'evidence_requests': [request(name)],
                'result': envelope.result.model_copy(update={'next_action': 'RETRIEVE',
                    'updated_issues': [retrieval_issue()],
                    'issue_transitions': [IssueTransition(issue_id='issue-coverage', from_status=None,
                        to_status='needs_retrieval', change_this_round='New coverage question',
                        basis_evidence_ids=[], basis_argument='Coverage requires the original source',
                        resolution_reason=None)]})})
        return envelope


class CaptureEngine(WorkflowEngine):
    def __init__(self, *args, reassess=False):
        super().__init__(*args)
        self.retrievals = []
        self.reassess = reassess

    async def investigate(self, run_id, key, questions, *, fresh=False, extra=None):
        self.retrievals.append({'key': key, 'questions': questions, 'fresh': fresh, **(extra or {})})
        return {'investigated': True}

    async def recheck_removed_claim_evidence(self, run_id, key):
        return {'rechecked': True} if self.reassess else None


def retrieval_issue():
    return Issue(issue_id='issue-coverage', claim_id='claim_observation', claim_version=1,
        content='Coverage is unresolved', status='needs_retrieval', evidence_ids=[],
        resolution_criterion='Inspect the original source', change_this_round='New coverage question',
        next_action='RETRIEVE')


@pytest.mark.asyncio
@pytest.mark.parametrize('retry', [False, True])
async def test_complete_requests_reach_retrieval_after_restore_and_explicit_retry(tmp_path, monkeypatch, retry):
    store, ledger, run, _ = setup_case(tmp_path, paused=retry)
    if retry:
        replacement = prepare_task_retry(store, ledger, run.run_id, KEY, REASON)['replacement_key']
    else:
        replacement = KEY
    runtime = RequestRuntime(store)
    engine = CaptureEngine(store, runtime, Settings())
    result = await engine.call(run.run_id, KEY, 'moderator')
    assert store.get_run(run.run_id).state[KEY + '_evidence_requests'] == [request('final').model_dump()]
    assert store.get_run(run.run_id).state[replacement + '_evidence_requests'] == [request('final').model_dump()]
    # Recreating the engine restores the accepted result without a model replay.
    engine = CaptureEngine(store, runtime, Settings())
    assert await engine.call(run.run_id, KEY, 'moderator') == result
    assert len(runtime.calls) == 1
    monkeypatch.setattr(store, 'get_issues', lambda _: [retrieval_issue()])
    await engine.process_ruling(run.run_id, 1, result)
    assert engine.retrievals == [{'key': 'round1.retrieval',
        'questions': ['Check final coverage?'], 'fresh': True,
        'issue_targets': [retrieval_issue().model_dump()],
        'evidence_requests': [request('final').model_dump()]}]


@pytest.mark.asyncio
async def test_after_evidence_alias_retains_only_final_requests(tmp_path):
    store, _, run, _ = setup_case(tmp_path, paused=False)
    runtime = RequestRuntime(store, needs_evidence=True)
    engine = CaptureEngine(store, runtime, Settings())
    await engine.call(run.run_id, KEY, 'moderator')
    state = store.get_run(run.run_id).state
    assert engine.retrievals[0]['evidence_requests'] == [request('initial').model_dump()]
    assert state[KEY + '_evidence_requests'] == [request('final').model_dump()]
    assert len(runtime.calls) == 2


@pytest.mark.asyncio
async def test_reassessment_retrieves_final_requests_not_superseded_ruling(tmp_path, monkeypatch):
    store, _, _ = research_store(tmp_path)
    card = store.save_card(research_draft())
    run = store.create_run('run', card_id=card.card_id, card_version=card.version, state={'research_flow':'legacy_debate_v1'})
    runtime = RequestRuntime(store)
    engine = CaptureEngine(store, runtime, Settings(max_rounds=1), reassess=True)
    monkeypatch.setattr(store, 'get_issues', lambda _: [retrieval_issue()])
    # Isolate the issue kernel; this test exercises the accepted-ruling handoff.
    monkeypatch.setattr(store, 'apply_issues', lambda run_id, *args, **kwargs:
        engine.checkpoint(run_id, **kwargs['state_patch']))
    await engine.debate(run.run_id)
    state = store.get_run(run.run_id).state
    assert state['final_ruling_task_key'] == KEY + '.evidence_reassessment'
    assert state[KEY + '_evidence_requests'] == [request('final').model_dump()]
    assert engine.retrievals[-1]['evidence_requests'] == [request('reassessment').model_dump()]
    assert engine.retrievals[-1]['questions'] == ['Check reassessment coverage?']
