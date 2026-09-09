"""Bounded regressions for explicitly selected full-card paths; no model calls."""
import json

import pytest

from arc.scientific import validate_scientific_review, validate_scientific_output_contract
from arc.validation import ProtocolViolation
from tests.test_scientific_cycle import setup_cycle, review, defect, resolution


def test_open_prior_finding_survives_a_second_recheck(tmp_path):
    store, _, _, card = setup_cycle(tmp_path)
    previous = review('needs_evidence', resolutions=[resolution('unresolved')])
    with pytest.raises(ProtocolViolation, match='ADDRESS_PREVIOUS_FINDINGS'):
        validate_scientific_review(store, card.draft, review(), previous=previous)
    continued = review('needs_evidence', resolutions=[resolution('unresolved')])
    assert validate_scientific_review(store, card.draft, continued, previous=previous) is continued
    resolved = review(resolutions=[resolution()])
    assert validate_scientific_review(store, card.draft, resolved, previous=previous) is resolved
    assert validate_scientific_review(store, card.draft, review(), previous=resolved)


@pytest.mark.parametrize('kind', ['string', 'claim'])
def test_deleting_preceding_array_item_does_not_remove_faulty_target(tmp_path, kind):
    store, _, _, card = setup_cycle(tmp_path)
    original = card.draft.model_copy(deep=True)
    if kind == 'string':
        original.minimal_test.measurements = ['unrelated measurement', 'faulty measurement']
        location, quote = '/minimal_test/measurements/1', 'faulty measurement'
        revised = original.model_copy(deep=True)
        revised.minimal_test.measurements.pop(0)
    else:
        from arc.schemas import Claim
        original.claims = [Claim(claim_id='unrelated', version=1, text='other', kind='logical',
                                conditions=[], evidence_ids=[]),
                           Claim(claim_id='faulty', version=1, text='faulty measurement', kind='logical',
                                 conditions=[], evidence_ids=[])]
        location, quote = '/claims/1/text', 'faulty measurement'
        revised = original.model_copy(deep=True)
        revised.claims.pop(0)
    previous = review('revise', findings=[defect(location=location, quoted_text=quote)])
    with pytest.raises(ProtocolViolation, match='FAULTY_FIELD_UNCHANGED'):
        validate_scientific_review(store, revised, review(resolutions=[resolution()]),
                                   previous=previous, previous_draft=original)


def test_associated_condition_repair_need_not_rewrite_measurement_label(tmp_path):
    store, _, _, card = setup_cycle(tmp_path)
    original = card.draft
    revised = original.model_copy(deep=True)
    revised.minimal_test.controls.append('Report each distance/interference cell separately.')
    assert revised.minimal_test.measurements == original.minimal_test.measurements
    previous = review('revise', findings=[defect()])
    assert validate_scientific_review(store, revised, review(resolutions=[resolution()]),
                                     previous=previous, previous_draft=original)


def test_removing_actual_faulty_array_item_is_allowed(tmp_path):
    store, _, _, card = setup_cycle(tmp_path)
    original = card.draft.model_copy(deep=True)
    original.minimal_test.measurements = ['valid measurement', 'faulty measurement']
    revised = original.model_copy(deep=True)
    revised.minimal_test.measurements.pop()
    previous = review('revise', findings=[defect(location='/minimal_test/measurements/1',
                                               quoted_text='faulty measurement')])
    assert validate_scientific_review(store, revised, review(resolutions=[resolution()]),
                                     previous=previous, previous_draft=original)


def test_relocation_failure_is_diagnosed_inside_output_correction_gate(tmp_path):
    store, _, _, card = setup_cycle(tmp_path)
    original = card.draft.model_copy(deep=True)
    original.minimal_test.measurements = ['other', 'faulty measurement']
    revised = original.model_copy(deep=True)
    revised.minimal_test.measurements.pop(0)
    previous = review('revise', findings=[defect(location='/minimal_test/measurements/1',
                                               quoted_text='faulty measurement')])
    with pytest.raises(ProtocolViolation, match='FAULTY_FIELD_UNCHANGED'):
        validate_scientific_output_contract(store, {
            'review_target': revised.model_dump(mode='json'),
            'previous_review_target': original.model_dump(mode='json'),
            'previous_review': previous.model_dump(mode='json')}, review(resolutions=[resolution()]))


@pytest.mark.asyncio
async def test_frozen_evidence_registration_uses_accepted_explicit_retry_identity(tmp_path):
    from arc.functional_evaluation import FrozenEngine
    from arc.scientific import _registered_support_findings
    from arc.schemas import Envelope, Finding, InvestigatorResult, Subject, TaskRecord
    from tests.test_scientific_recovery import setup_support
    store, run, card, _, _ = setup_support(tmp_path)
    source = store.get_record('src_synthetic')
    claim = card.draft.claims[0]
    excerpt = 'Moving relevant facts farther away lowered recall. Distractor count also changed.'
    start = source['content'].index(excerpt)
    result = InvestigatorResult(questions_addressed=['Reassess support'], actual_searches=[],
        findings=[Finding(claim=claim.text, claim_id=claim.claim_id, claim_version=claim.version,
            conditions=claim.conditions, source_id=source['source_id'],
            locator=f'chars:{start}:{start+len(excerpt)}', locator_status='verified',
            relation='limits', origin='original', excerpt=excerpt,
            support_explanation='Joint change does not establish which factor is causal.')],
        contrary_findings=[], source_access_limits=[], implications_for_current_card=[],
        unresolved_questions=[], recommended_next_action='STOP')
    key = 'science.support_recheck'
    physical = f'{run.run_id}.{key}.protocol_retry1'
    subject = Subject(run_id=run.run_id, campaign_id=run.campaign_id,
                      card_id=card.card_id, card_version=card.version)
    envelope = Envelope[InvestigatorResult](schema_version='arc.v1', task_id=physical,
        subject=subject, result_status='complete', result=result, evidence_requests=[],
        capability_requests=[], note=None)
    prompt = store.save_artifact('tests/retry-investigator-prompt.json',
                                 json.dumps({'prompt_id': 'investigator.INVOKE'}))
    response = store.save_artifact('tests/retry-investigator-response.json', envelope.model_dump_json())
    store.put_task(TaskRecord(task_id=physical, run_id=run.run_id, input_hash='fixture',
        prompt_hash='fixture', model_config_hash='fixture', status='ACCEPTED',
        rendered_prompt_path=prompt, response_artifact_path=response,
        accepted_result=envelope.model_dump(mode='json')))
    store.update_run(run.run_id, state={**run.state,
        'comparison_envelopes': {key: envelope.model_dump(mode='json')}})

    class SavedRuntime:
        async def close(self):
            pass
        async def invoke(self, **kwargs):
            raise AssertionError('An accepted retry must not call the model again')

    async def factory(*args):
        return SavedRuntime()

    engine = FrozenEngine(store, None, None, {
        'evidence': [], 'sources': [source], 'topic': 'Controlled recall'}, factory)
    accepted = await engine.investigate(run.run_id, key, ['Reassess support'])
    records = _registered_support_findings(engine, run.run_id, key, accepted, card)
    expected = store.validate_findings(result.findings, task_id=physical,
                                       allowed_claims=card.draft.claims)
    assert [record.evidence_id for record in records] == [record.evidence_id for record in expected]
    assert engine.trace_tasks(run.run_id, key) == [physical]
    count = len(store.list_evidence())
    await engine.investigate(run.run_id, key, ['Reassess support'])
    assert len(store.list_evidence()) == count
