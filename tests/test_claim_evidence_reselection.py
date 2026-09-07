"""Old-target removal triggers bounded evidence work, never recycled support."""
from collections import Counter
from copy import deepcopy
import json

import pytest

from arc.config import Settings
from arc.schemas import DeveloperResult, Envelope, TaskRecord
from arc.store import StateError, claim_fingerprint
from arc.validation import remove_superseded_claim_evidence
from arc.workflows import WorkflowEngine, WorkflowPause
from .test_claim_targets import revision_payload
from .test_claim_versions import ConditionsRuntime, workflow_case
from .test_workflows import ScriptedRuntime


def test_all_proposed_claims_remove_only_earlier_same_id_targets(tmp_path):
    store, card, _, _, old = workflow_case(tmp_path, keep_evidence=True)
    draft = card.draft.model_dump(mode='json')
    draft['claims'][0]['version'] = 2  # Already incremented by the model.
    other = deepcopy(draft['claims'][0])
    other.update(claim_id='another_claim', version=7)
    draft['claims'].append(other)
    result = DeveloperResult.model_validate(revision_payload(card.draft.model_dump(mode='json'), draft))
    raw = result.model_dump(mode='json')
    derived, removed = remove_superseded_claim_evidence(store, result)
    assert derived.proposed_revision.claims[0].evidence_ids == []
    assert derived.proposed_revision.claims[1].evidence_ids == [old.evidence_id]
    assert removed == [{'claim_id': old.claim_id, 'claim_version': 2, 'evidence_id': old.evidence_id,
        'evidence_claim_version': 1, 'source_id': old.source_id, 'evidence_verification_status': 'verified',
        'reason': 'superseded_same_claim_target'}]
    assert result.model_dump(mode='json') == raw
    assert store.get_card(card.card_id).draft.claims[0].evidence_ids == [old.evidence_id]
    assert store.list_evidence(ids=[old.evidence_id])[0] == old


@pytest.mark.parametrize('bad_reference', ['unknown', 'future'])
def test_unknown_and_future_evidence_references_are_not_removed_or_accepted(tmp_path, bad_reference):
    store, card, _, _, old = workflow_case(tmp_path, keep_evidence=True)
    draft = card.draft.model_copy(deep=True)
    if bad_reference == 'future':
        future = old.model_copy(update={'evidence_id': 'ev_future', 'claim_version': 3})
        store.register_evidence(future)
        target, error = future.evidence_id, 'claim_evidence_version_mismatch'
    else:
        target, error = 'not_registered', 'unknown_evidence_id'
    draft.claims[0].version = 2
    draft.claims[0].evidence_ids = [old.evidence_id, target]
    result = DeveloperResult.model_validate(revision_payload(card.draft.model_dump(mode='json'), draft.model_dump(mode='json')))
    derived, removed = remove_superseded_claim_evidence(store, result)
    assert derived.proposed_revision.claims[0].evidence_ids == [target] and len(removed) == 1
    with pytest.raises(StateError, match=error):
        store.validate_claim_dependencies(card, derived.proposed_revision)


class ReselectionRuntime(ConditionsRuntime):
    def __init__(self, store, *, mode='developer', repeat=False, pause_at=None, crash_at=None, empty_recheck=False):
        super().__init__(store, mode=mode, keep_evidence=True)
        self.repeat, self.pause_at, self.crash_at = repeat, pause_at, crash_at
        self.empty_recheck = empty_recheck
        self.interrupted = False

    async def invoke(self, **kwargs):
        target = kwargs['task_id']
        if not self.interrupted and ((self.pause_at and target.endswith(self.pause_at))
                                     or (self.crash_at and target.endswith(self.crash_at))):
            self.interrupted = True
            if self.crash_at:
                raise SystemExit('Synthetic process exit before reassessment request.')
            raise WorkflowPause('PAUSED_BUDGET', 'synthetic_not_admitted')
        return await super().invoke(**kwargs)

    def reply(self, role, task, payload, task_id):
        if role == 'moderator' and task_id.endswith('.evidence_reassessment'):
            result = ScriptedRuntime.reply(self, role, task, payload, task_id)
            result.update(assessment='NEEDS_EVIDENCE', concise_ruling='NEW_RULING_FROM_RECHECK')
            current = payload['card']['draft']['claims'][0]
            result['decisive_evidence_ids'] = [e.evidence_id for e in self.store.list_evidence()
                if (e.claim_id, e.claim_version) == (current['claim_id'], current['version'])]
            if self.repeat:
                result['proposed_card_revision'] = deepcopy(payload['card']['draft'])
                result['proposed_card_revision']['claims'][0]['evidence_ids'] = ['ev_synthetic']
            return result
        result = super().reply(role, task, payload, task_id)
        if role == 'developer':
            # Covers the real shape: the model already supplied v2 but reused v1 evidence.
            result['proposed_revision']['claims'][0]['version'] = 2
            result['evidence_review'][0]['claim_version'] = 2
        if role == 'moderator' and self.mode == 'moderator':
            result['concise_ruling'] = 'OLD_RULING_MUST_NOT_BE_ACCEPTED'
            result['updated_issues'] = [{'issue_id': 'unaccepted_issue', 'claim_id': 'claim_observation',
                'claim_version': 1, 'claim_kind': 'empirical', 'content': 'Unsupported resolution.',
                'status': 'resolved', 'evidence_ids': ['ev_synthetic'], 'resolution_criterion': 'New-target evidence.',
                'change_this_round': 'The old ruling incorrectly claims resolution.', 'next_action': 'STOP'}]
            result['issue_transitions'] = [{'issue_id': 'unaccepted_issue', 'from_status': None,
                'to_status': 'resolved', 'change_this_round': 'Incorrect old conclusion.',
                'basis_evidence_ids': ['ev_synthetic'], 'basis_argument': None, 'resolution_reason': 'Old assertion.'}]
        if role == 'investigator' and task_id.endswith('.evidence_recheck'):
            current = payload['card']['draft']['claims'][0]
            excerpt = 'The authors ask whether distance or interference caused the result; they do not isolate the variables.'
            body = self.store.get_record('src_synthetic')['content']
            start = body.index(excerpt)
            result['findings'] = [{'claim_id': current['claim_id'], 'claim_version': current['version'],
                'claim': current['text'], 'conditions': current['conditions'], 'source_id': 'src_synthetic',
                'locator': f'chars:{start}:{start + len(excerpt)}', 'locator_status': 'verified',
                'relation': 'limits', 'origin': 'original', 'excerpt': excerpt,
                'support_explanation': 'This synthetic passage leaves the causal separation untested; it does not establish the newly restricted condition.'}]
            result['unresolved_questions'] = ['The narrower positive-control condition remains untested.']
            if self.empty_recheck:
                result['findings'] = []
        return result


@pytest.mark.asyncio
async def test_new_targeted_finding_enters_debate_without_rebinding_old_record(tmp_path):
    store, original, run, _, old = workflow_case(tmp_path, keep_evidence=True)
    runtime = ReselectionRuntime(store)
    result = await WorkflowEngine(store, runtime, Settings()).execute(run.run_id)
    assert result.status == 'COMPLETED'
    current = store.get_card(original.card_id).draft.claims[0]
    assert current.version == 2 and current.evidence_ids == []
    new = [e for e in store.list_evidence(run_id=run.run_id) if e.claim_id == current.claim_id]
    assert len(new) == 1 and new[0].claim_version == 2 and new[0].relation == 'limits'
    assert new[0].evidence_id != old.evidence_id and new[0].target_claim_fingerprint == claim_fingerprint(current)
    assert store.list_evidence(ids=[old.evidence_id])[0] == old
    proposer = next(c for c in runtime.calls if c['role'] == 'proposer')
    assert new[0].evidence_id in {e['evidence_id'] for e in proposer['payload']['evidence']}
    assert 'development' in proposer['payload']['claim_evidence_reselection']
    task = store.get_task(f'{run.run_id}.development')
    assert task.accepted_result['result']['proposed_revision']['claims'][0]['evidence_ids'] == [old.evidence_id]
    before = len(runtime.calls)
    assert (await WorkflowEngine(store, runtime, Settings()).execute(run.run_id)).status == 'COMPLETED'
    assert len(runtime.calls) == before and len(store.list_evidence(run_id=run.run_id)) == 1


@pytest.mark.asyncio
async def test_moderator_reassessment_replaces_unapplied_ruling_and_issue_transitions(tmp_path):
    store, card, run, _, old = workflow_case(tmp_path, mode='run', keep_evidence=True)
    runtime = ReselectionRuntime(store, mode='moderator')
    result = await WorkflowEngine(store, runtime, Settings(max_rounds=1)).execute(run.run_id)
    assert result.status == 'COMPLETED' and result.assessment == 'NEEDS_EVIDENCE'
    assert result.state['rounds_completed'] == 1
    assert result.state['final_ruling']['concise_ruling'] == 'NEW_RULING_FROM_RECHECK'
    assert store.get_issues(run.run_id) == []
    assert Counter(c['role'] for c in runtime.calls) == {'proposer': 1, 'skeptic': 1, 'moderator': 2, 'investigator': 1}
    followup = next(c for c in runtime.calls if c['task_id'].endswith('.evidence_reassessment'))
    assert followup['payload']['superseded_ruling']['status'] == 'not_applied_after_evidence_removal'
    assert followup['payload']['card']['draft']['claims'][0]['version'] == 2
    assert followup['payload']['evidence_recheck']['findings'][0]['claim_version'] == 2
    assert store.get_task(f'{run.run_id}.round1.moderator').accepted_result['result']['updated_issues'][0]['status'] == 'resolved'
    assert store.list_evidence(ids=[old.evidence_id])[0] == old


@pytest.mark.asyncio
@pytest.mark.parametrize('pause_at', ['.evidence_recheck', '.evidence_reassessment'])
async def test_budget_pause_resumes_bounded_chain_without_replaying_completed_roles(tmp_path, pause_at):
    store, _, run, _, _ = workflow_case(tmp_path, mode='run', keep_evidence=True)
    runtime = ReselectionRuntime(store, mode='moderator', pause_at=pause_at)
    engine = WorkflowEngine(store, runtime, Settings(max_rounds=1))
    paused = await engine.execute(run.run_id)
    assert paused.status == 'PAUSED_BUDGET' and paused.assessment is None
    assert store.get_card(paused.card_id).version == paused.card_version == 2
    assert not paused.state.get('final_ruling') and store.get_issues(run.run_id) == []
    accepted_before = {c['task_id'] for c in runtime.calls}
    result = await WorkflowEngine(store, runtime, Settings(max_rounds=1)).execute(run.run_id)
    assert result.status == 'COMPLETED' and result.assessment == 'NEEDS_EVIDENCE'
    assert store.get_card(result.card_id).version == result.card_version == 2
    counts = Counter(c['task_id'] for c in runtime.calls)
    assert all(counts[task_id] == 1 for task_id in accepted_before)
    assert Counter(c['role'] for c in runtime.calls)['investigator'] == 1


@pytest.mark.asyncio
async def test_process_exit_after_registered_recheck_resumes_without_duplicate_findings(tmp_path):
    store, _, run, _, _ = workflow_case(tmp_path, mode='run', keep_evidence=True)
    runtime = ReselectionRuntime(store, mode='moderator', crash_at='.evidence_reassessment')
    with pytest.raises(SystemExit):
        await WorkflowEngine(store, runtime, Settings(max_rounds=1)).execute(run.run_id)
    before = store.list_evidence(run_id=run.run_id)
    assert len(before) == 1
    result = await WorkflowEngine(store, runtime, Settings(max_rounds=1)).execute(run.run_id)
    assert result.status == 'COMPLETED' and store.list_evidence(run_id=run.run_id) == before
    assert Counter(c['role'] for c in runtime.calls)['investigator'] == 1


@pytest.mark.asyncio
async def test_reassessment_repeating_stale_reference_stops_without_another_loop(tmp_path):
    store, _, run, _, _ = workflow_case(tmp_path, mode='run', keep_evidence=True)
    runtime = ReselectionRuntime(store, mode='moderator', repeat=True)
    engine = WorkflowEngine(store, runtime, Settings(max_rounds=1))
    result = await engine.execute(run.run_id)
    assert result.status == 'PAUSED_PROTOCOL'
    assert result.stop_reason == 'superseded_evidence_repeated_after_reassessment'
    assert result.assessment is None and not result.state.get('final_ruling')
    assert store.get_issues(run.run_id) == []
    assert Counter(c['role'] for c in runtime.calls)['moderator'] == 2
    assert Counter(c['role'] for c in runtime.calls)['investigator'] == 1
    before = len(runtime.calls)
    assert (await engine.execute(run.run_id)).status == 'PAUSED_PROTOCOL'
    assert len(runtime.calls) == before


@pytest.mark.asyncio
async def test_missing_new_support_can_end_in_needs_evidence_without_fabricated_binding(tmp_path):
    store, _, run, _, old = workflow_case(tmp_path, mode='run', keep_evidence=True)
    runtime = ReselectionRuntime(store, mode='moderator', empty_recheck=True)
    result = await WorkflowEngine(store, runtime, Settings(max_rounds=1)).execute(run.run_id)
    assert result.status == 'COMPLETED' and result.assessment == 'NEEDS_EVIDENCE'
    assert store.get_card(result.card_id).draft.claims[0].evidence_ids == []
    assert store.list_evidence(run_id=run.run_id) == []
    assert store.list_evidence(ids=[old.evidence_id])[0] == old
    followup = next(c for c in runtime.calls if c['task_id'].endswith('.evidence_reassessment'))
    assert followup['payload']['evidence_recheck']['findings'] == []
    assert followup['payload']['evidence_recheck']['unresolved_questions']


@pytest.mark.asyncio
async def test_reassessment_chain_preserves_normal_bounded_evidence_requests(tmp_path):
    store, _, run, _, _ = workflow_case(tmp_path, mode='run', keep_evidence=True)

    class MoreEvidence(ReselectionRuntime):
        def reply(self, role, task, payload, task_id):
            if role == 'moderator' and '.evidence_reassessment.after_evidence' in task_id:
                result = ScriptedRuntime.reply(self, role, task, payload, task_id)
                result.update(assessment='NEEDS_EVIDENCE', concise_ruling='Reassessed after a normal bounded request.')
                return result
            return super().reply(role, task, payload, task_id)

        async def invoke(self, **kwargs):
            if not kwargs['task_id'].endswith('.evidence_reassessment'):
                return await super().invoke(**kwargs)
            task_id, subject = kwargs['task_id'], kwargs['subject']
            self.calls.append({'role': kwargs['role'], 'task_id': task_id,
                               'payload': deepcopy(kwargs['payload'])})
            envelope = Envelope[kwargs['result_schema']](schema_version='arc.v1', task_id=task_id,
                subject=subject, result_status='needs_evidence', result=None, capability_requests=[],
                note='The new claim still lacks a decisive source.', evidence_requests=[{
                    'request_local_id': 'missing_new_condition', 'claim_id': 'claim_observation',
                    'issue_id': None, 'draw_id': None, 'question': 'Does the new control condition hold?',
                    'target_source_ids': ['src_synthetic'], 'queries': [],
                    'purpose': 'Establish the current claim boundary.', 'decision_if_supported': 'Reassess feasibility.',
                    'decision_if_contradicted': 'Retain the narrower unsupported claim as unresolved.'}])
            path = store.save_artifact(f'tests/{task_id}.json', envelope.model_dump_json())
            store.put_task(TaskRecord(task_id=task_id, run_id=subject.run_id, input_hash='synthetic-input',
                prompt_hash='synthetic-prompt', model_config_hash='synthetic-model', status='PAUSED_EXTERNAL',
                response_artifact_path=path))
            return envelope

    runtime = MoreEvidence(store, mode='moderator')
    result = await WorkflowEngine(store, runtime, Settings(max_rounds=1)).execute(run.run_id)
    assert result.status == 'COMPLETED'
    assert result.state['pending_evidence_requests'][0]['request_local_id'] == 'missing_new_condition'
    assert result.assessment == 'NEEDS_EVIDENCE'
    assert result.state['rounds_completed'] == 1
    assert result.state['final_ruling']['concise_ruling'] == 'Reassessed after a normal bounded request.'
    assert Counter(c['role'] for c in runtime.calls)['moderator'] == 3
    assert Counter(c['role'] for c in runtime.calls)['investigator'] == 2
    assert any('.evidence_reassessment.requested_evidence' in c['task_id'] for c in runtime.calls)
