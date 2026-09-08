"""Scientific correction behavior with local synthetic cards; no paid calls."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from arc.research_context import build_research_context
from arc.schemas import (Claim, ConceptionResult, ScientificFinding, ScientificReview,
                         ScientificRevision, TaskRecord, RESULT_SCHEMAS)
from arc.scientific import (apply_scientific_revision, discover, review_and_revise,
                            validate_scientific_review)
from arc.validation import ProtocolViolation
from tests.test_selection import research_store, research_draft


def defect(**changes):
    payload = dict(finding_id='missing_measure', location='/minimal_test/measurements',
        quoted_text='fact recall accuracy',
        reason='The comparison needs a response for each intervention, not only pooled accuracy.',
        consequence='Pooled accuracy cannot distinguish the two proposed explanations.',
        evidence_ids=[], source_ids=[], severity='repairable',
        required_change='Record recall separately for each intervention condition.',
        acceptance_test='Each intervention condition has an observed recall value.')
    payload.update(changes)
    return ScientificFinding.model_validate(payload)


def review(action='retain', *, findings=None, resolutions=None, edits=None, **changes):
    payload = dict(original_question='Separate distance from interference under equal budget.',
        scope_faithful=True, core_insight='Separating the interventions changes which remedy is justified.',
        value_judgment='substantial', value_reason='The competing explanations recommend different interventions.',
        verification_work=[dict(question='Can pooled accuracy separate the interventions?',
            method='counterexample', answer='Opposite cell changes can cancel in pooled accuracy.',
            evidence_ids=[], source_ids=[])],
        decisive_findings=[] if findings is None else [item.model_dump() for item in findings],
        prior_findings=[] if resolutions is None else resolutions,
        edit_assessments=[] if edits is None else edits,
        remaining_uncertainty=['Transfer beyond this controlled task is untested.'], action=action)
    payload.update(changes)
    return ScientificReview.model_validate(payload)


def resolution(status='resolved'):
    return dict(finding_id='missing_measure', status=status,
                reason='The current protocol now records every intervention condition separately.')


def patch(draft, *, risk_only=False):
    if risk_only:
        value = draft.risks.model_dump(mode='json')
        value['decisive_risks'].append('Pooled accuracy cannot distinguish the explanations.')
        field = 'risks'
    else:
        value = draft.minimal_test.model_dump(mode='json')
        value['measurements'] = ['fact recall accuracy separately for every distance/interference cell']
        field = 'minimal_test'
    return ScientificRevision.model_validate(dict(section_updates=[dict(field=field, value=value)],
        claim_updates=[], remove_claim_ids=[], addressed_findings=[resolution()],
        change_summary=['Replace pooled measurement with per-condition observation.'], abandon=False))


class CheckpointEngine:
    """Only model responses are fake; cards, draws and checkpoints use the real store."""
    def __init__(self, store, outputs, *, interrupt_before=None):
        self.store = store
        self.outputs = outputs
        self.invocations = []
        self.payloads = {}
        self.interrupt_before = interrupt_before

    def context(self, run_id):
        return build_research_context(self.store, self.store.get_run(run_id))

    def checkpoint(self, run_id, **updates):
        state = dict(self.store.get_run(run_id).state)
        state.update(updates)
        self.store.update_run(run_id, state=state)
        return state

    async def call(self, run_id, key, role, task='INVOKE', payload=None,
                   on_admitted=None, tool_profile=None):
        run = self.store.get_run(run_id)
        schema = RESULT_SCHEMAS[f'{role}.{task}' if role == 'discovery' else role]
        if key in run.state:
            return schema.model_validate(run.state[key])
        inputs = dict(run.state.get('task_inputs', {}))
        inputs.setdefault(key, {'payload': deepcopy(payload), 'subject': {
            'campaign_id': run.campaign_id, 'run_id': run_id,
            'card_id': run.card_id, 'card_version': run.card_version}})
        self.checkpoint(run_id, task_inputs=inputs)
        self.payloads[key] = deepcopy(inputs[key]['payload'])
        if self.interrupt_before == key:
            self.interrupt_before = None
            raise InterruptedError('Synthetic interruption before this model response')
        if on_admitted:
            on_admitted()
        self.invocations.append(key)
        result = self.outputs[key]
        response = {'result_status': 'complete', 'result': result.model_dump(mode='json'),
                    'subject': inputs[key]['subject']}
        response_path = f'synthetic/{run_id}.{key}.json'
        self.store.save_artifact(response_path, json.dumps(response))
        prompt_path = f'synthetic/{run_id}.{key}.prompt.json'
        self.store.save_artifact(prompt_path, json.dumps({'prompt_id': f'{role}.{task}'}))
        self.store.put_task(TaskRecord(task_id=f'{run_id}.{key}', run_id=run_id,
            input_hash='synthetic-input', prompt_hash='synthetic-prompt',
            model_config_hash='synthetic-config', status='ACCEPTED',
            response_artifact_path=response_path, rendered_prompt_path=prompt_path, accepted_result=response))
        self.checkpoint(run_id, **{key: result.model_dump(mode='json')})
        return result

    def trace_tasks(self, run_id, key):
        return [f'{run_id}.{key}']

    async def investigate(self, *args, **kwargs):
        raise AssertionError('No evidence changed: the local correction must not repurchase evidence')

    async def archive_compare(self, *args, **kwargs):
        return {'comparisons': []}

    def complete(self, run_id, reason):
        self.store.update_run(run_id, status='COMPLETED', stop_reason=reason)


def setup_cycle(tmp_path, *, select_original=False):
    store, source, evidence = research_store(tmp_path)
    campaign = store.create_campaign('Separate distance from interference under equal budget.',
                                     ['Keep both interventions and equal budget'], max_draws=1)
    run = store.create_run('discover', campaign_id=campaign.campaign_id,
        state={'evidence_ids': [evidence.evidence_id]})
    original = store.save_card(research_draft(), run_id=run.run_id)
    if select_original:
        from tests.test_selection import selection_result
        store.record_selection(run.run_id, original.card_id, original.version, selection_result())
        original = store.get_card(original.card_id, original.version)
    return store, campaign, store.get_run(run.run_id), original


@pytest.mark.parametrize('change', [
    {'findings': [defect()]},
    {'scope_faithful': False},
    {'value_judgment': 'routine'},
    {'resolutions': [resolution('unresolved')]},
])
def test_retention_cannot_override_decisive_errors_or_routine_value(change):
    with pytest.raises(ValidationError, match='retention_requires'):
        review('retain', **change)


@pytest.mark.parametrize('location,quote', [
    ('minimal_test/measurements', 'fact recall accuracy'),
    ('/minimal_test/nonexistent', ''),
    ('/minimal_test/measurements/-1', 'fact recall accuracy'),
    ('/minimal_test/measurements/01', ''),
    ('/minimal_test/measurements/9', ''),
    ('/minimal_test/measurements/0', 'a nonexistent measurement'),
])
def test_findings_must_point_to_the_actual_error_not_an_invented_or_invalid_location(tmp_path, location, quote):
    store, _, _, original = setup_cycle(tmp_path)
    result = review('revise', findings=[defect(location=location, quoted_text=quote)])
    with pytest.raises(ProtocolViolation):
        validate_scientific_review(store, original.draft, result)


def test_missing_component_can_reference_existing_container_with_empty_quote(tmp_path):
    store, _, _, original = setup_cycle(tmp_path)
    result = review('revise', findings=[defect(location='/minimal_test/controls', quoted_text='')])
    assert validate_scientific_review(store, original.draft, result) is result


def test_repeating_same_section_does_not_count_as_scientific_revision(tmp_path):
    _, _, _, original = setup_cycle(tmp_path)
    revision = patch(original.draft)
    revision.section_updates[0].value = original.draft.minimal_test.model_dump(mode='json')
    with pytest.raises(ProtocolViolation):
        apply_scientific_revision(original, revision)


@pytest.mark.asyncio
async def test_risk_acknowledgment_cannot_leave_the_original_error_and_claim_it_resolved(tmp_path):
    store, _, run, original = setup_cycle(tmp_path)
    engine = CheckpointEngine(store, {
        'science.review': review('revise', findings=[defect()]),
        'science.revision': patch(original.draft, risk_only=True),
        'science.recheck': review('retain', resolutions=[resolution()]),
    })
    with pytest.raises(ProtocolViolation):
        await review_and_revise(engine, run.run_id, 'science')
    assert store.get_card(original.card_id).selection is None


@pytest.mark.asyncio
async def test_independent_recheck_can_retract_an_incorrect_original_objection(tmp_path):
    store, _, run, original = setup_cycle(tmp_path)
    corrected_review = resolution('reviewer_error')
    corrected_review['reason'] = 'The measurement was already explicitly conditional on the intervention in the protocol.'
    engine = CheckpointEngine(store, {
        'science.review': review('revise', findings=[defect()]),
        'science.revision': patch(original.draft, risk_only=True),
        'science.recheck': review('retain', resolutions=[corrected_review]),
    })
    current, result = await review_and_revise(engine, run.run_id, 'science')
    assert current.draft.minimal_test == original.draft.minimal_test
    assert result.prior_findings[0].status == 'reviewer_error'
    assert result.action == 'retain'


@pytest.mark.asyncio
async def test_correct_card_finishes_after_one_review_without_mandatory_revision(tmp_path):
    store, _, run, original = setup_cycle(tmp_path)
    engine = CheckpointEngine(store, {'science.review': review()})
    current, result = await review_and_revise(engine, run.run_id, 'science')
    assert engine.invocations == ['science.review']
    assert current.version == original.version and result.action == 'retain'
    assert len(store.list_cards(run_id=run.run_id)) == 1


@pytest.mark.asyncio
async def test_revision_is_rechecked_under_original_task_and_does_not_inherit_old_recommendation(tmp_path):
    store, campaign, run, original = setup_cycle(tmp_path, select_original=True)
    initial = review('revise', findings=[defect()])
    engine = CheckpointEngine(store, {
        'science.review': initial, 'science.revision': patch(original.draft),
        'science.recheck': review('needs_evidence', resolutions=[resolution()],
                                 remaining_uncertainty=['The closest work could already establish the difference.']),
    }, interrupt_before='science.recheck')
    with pytest.raises(InterruptedError):
        await review_and_revise(engine, run.run_id, 'science')
    assert 'scientific_cycles' not in store.get_run(run.run_id).state
    assert store.get_card(original.card_id).version == original.version
    current, result = await review_and_revise(engine, run.run_id, 'science')
    assert current.version == original.version + 1
    assert current.selection is None and current.selection_result is None
    assert result.action == 'needs_evidence'
    assert store.get_card(original.card_id, original.version).selection == 'MAIN_REPORT'
    assert engine.invocations == ['science.review', 'science.revision', 'science.recheck']
    for key in ['science.review', 'science.revision', 'science.recheck']:
        assert engine.payloads[key]['original_task']['topic'] == campaign.topic
        assert engine.payloads[key]['original_task']['boundaries'] == campaign.boundaries
    assert engine.payloads['science.recheck']['review_target']['minimal_test']['measurements'] != \
        engine.payloads['science.review']['review_target']['minimal_test']['measurements']
    await review_and_revise(engine, run.run_id, 'science')
    assert engine.invocations == ['science.review', 'science.revision', 'science.recheck']
    assert len(store.list_cards(run_id=run.run_id)) == 2


@pytest.mark.asyncio
async def test_recheck_must_resolve_each_original_finding_not_silently_drop_it(tmp_path):
    store, _, run, original = setup_cycle(tmp_path)
    engine = CheckpointEngine(store, {
        'science.review': review('revise', findings=[defect()]),
        'science.revision': patch(original.draft), 'science.recheck': review(),
    })
    with pytest.raises(ProtocolViolation, match='ADDRESS_PREVIOUS_FINDINGS'):
        await review_and_revise(engine, run.run_id, 'science')
    assert store.get_card(original.card_id).version == 1


@pytest.mark.asyncio
async def test_interruption_after_revised_card_save_resumes_without_duplicate_card_or_paid_step(tmp_path, monkeypatch):
    store, _, run, original = setup_cycle(tmp_path)
    engine = CheckpointEngine(store, {
        'science.review': review('revise', findings=[defect()]),
        'science.revision': patch(original.draft),
        'science.recheck': review('retain', resolutions=[resolution()]),
    })
    real_checkpoint = engine.checkpoint
    interrupted = False

    def fail_last_checkpoint(run_id, **updates):
        nonlocal interrupted
        if 'scientific_cycles' in updates and not interrupted:
            interrupted = True
            raise InterruptedError('Synthetic stop after card save and before cycle completion')
        return real_checkpoint(run_id, **updates)

    monkeypatch.setattr(engine, 'checkpoint', fail_last_checkpoint)
    with pytest.raises(InterruptedError):
        await review_and_revise(engine, run.run_id, 'science')
    assert store.get_card(original.card_id).version == 2
    current, result = await review_and_revise(engine, run.run_id, 'science')
    assert current.version == 2 and result.action == 'retain'
    assert len(store.list_cards(run_id=run.run_id)) == 2
    assert engine.invocations == ['science.review', 'science.revision', 'science.recheck']


@pytest.mark.asyncio
async def test_one_draw_includes_revision_and_recheck_without_refreshing_quota(tmp_path):
    store, _, evidence = research_store(tmp_path)
    campaign = store.create_campaign('Separate distance and interference.', ['Equal budget'], max_draws=1)
    run = store.create_run('discover', campaign_id=campaign.campaign_id,
                           state={'evidence_ids': [evidence.evidence_id]})
    draft = research_draft()
    engine = CheckpointEngine(store, {
        'draw1.conception': ConceptionResult(card_candidate=draft, continue_or_stop='CONTINUE',
            composition_reason='Interventions distinguish remedies.', distinct_from_retained='First candidate.'),
        'draw1.science.review': review('revise', findings=[defect()]),
        'draw1.science.revision': patch(draft),
        'draw1.science.recheck': review('retain', resolutions=[resolution()]),
    })
    await discover(engine, run.run_id)
    assert store.get_campaign(campaign.campaign_id).draws_started == 1
    assert store.get_run(run.run_id).status == 'COMPLETED'
    assert len(store.get_run(run.run_id).state['draws']) == 1
    cards = store.list_cards(run_id=run.run_id)
    assert len({card.card_id for card in cards}) == 1
    final = max(cards, key=lambda card: card.version)
    assert final.version == 2 and final.selection == 'MAIN_REPORT'
    before = list(engine.invocations)
    await discover(engine, run.run_id)
    assert engine.invocations == before
    assert store.get_campaign(campaign.campaign_id).draws_started == 1


def test_unchanged_claim_cannot_be_rebound_to_an_arbitrary_old_version(tmp_path):
    store, _, evidence = research_store(tmp_path)
    draft = research_draft()
    draft.claims = [Claim(claim_id='claim_observation', version=3,
        text='Distance and distractor count covary in an observed recall decrease.',
        conditions=['synthetic controlled recall task'], kind='empirical', evidence_ids=[])]
    original = store.save_card(draft)
    revision = ScientificRevision(section_updates=[], claim_updates=[draft.claims[0].model_copy(
        update={'version': 1, 'evidence_ids': [evidence.evidence_id]})], remove_claim_ids=[],
        addressed_findings=[], change_summary=['Reuse earlier evidence without changing meaning.'], abandon=False)
    from arc.validation import derive_claim_versions
    from arc.store import StateError
    with pytest.raises((ProtocolViolation, StateError, ValueError)):
        candidate = apply_scientific_revision(original, revision)
        candidate, _, _ = derive_claim_versions(original, candidate,
            edit_assessments=[])
        store.save_card(candidate, card_id=original.card_id, parent_version=original.version)
    assert store.get_card(original.card_id).version == 1
