"""Local support review receives a bounded focus without suppressing science."""
from copy import deepcopy

import pytest

from arc.schemas import Claim
from arc.scientific import review_and_revise
from tests.test_scientific_cycle import CheckpointEngine, defect, review
from tests.test_scientific_recovery import SupportEngine, setup_support


def local_change(tmp_path, *, counting_error=False):
    store, run, old, proposed, initial = setup_support(tmp_path)
    draft = old.draft.model_copy(deep=True)
    draft.claims.append(Claim(claim_id='unchanged_hypothesis', version=1,
        text='The joint change could isolate distance from distractors.',
        conditions=['synthetic task'], kind='hypothesis', evidence_ids=[]))
    if counting_error:
        draft.resources.workload_assumptions.data_amount = '100K images across four conditions, 20K per condition.'
    original = store.save_card(draft, run_id=run.run_id)
    target = original.draft.model_copy(deep=True)
    target.claims[0] = proposed.claims[0]
    return store, store.get_run(run.run_id), original, target, initial


@pytest.mark.asyncio
async def test_local_support_scope_lists_only_changed_target_and_replacement_support(tmp_path):
    store, run, original, proposed, initial = local_change(tmp_path)
    engine = SupportEngine(store, {'science.review': initial, 'science.support_review': review()})
    card, _ = await review_and_revise(engine, run.run_id, 'science', original=original, proposed=proposed)
    payload = engine.payloads['science.support_review']
    scope = payload['support_review_scope']
    assert scope['kind'] == 'affected_support'
    assert scope['affected_claims'] == [{'claim_id': proposed.claims[0].claim_id, 'version': 2,
        'change_reason': initial.edit_assessments[0].reason}]
    assert scope['unchanged_claim_ids'] == ['unchanged_hypothesis']
    assert [item['evidence_id'] for item in scope['removed_bindings']] == ['ev_synthetic']
    assert scope['registered_evidence_ids'] == card.draft.claims[0].evidence_ids
    binding = scope['replacement_bindings'][0]
    assert binding['claim_version'] == binding['evidence_claim_version'] == 2
    assert binding['binding'] == 'current_claim_target' and binding['relation'] == 'limits'
    assert binding['verification_transferred'] is False
    assert binding['support_semantics'] == 'requires_scientific_review_not_proven_by_source_verification'
    assert scope['support_recheck']['findings'][0]['support_explanation'].startswith('The passage supports only')
    assert payload['previous_review'] == initial.model_dump(mode='json')
    assert len(payload['review_target']['claims']) == 2
    assert payload['original_task']['topic'] == store.get_campaign(run.campaign_id).topic
    assert 'support_review_scope' not in engine.payloads['science.review']


@pytest.mark.asyncio
async def test_reviewed_equivalent_expression_reuses_support_without_new_support_task(tmp_path):
    store, run, original, proposed, _ = setup_support(tmp_path)
    proposed.claims[0].text = original.draft.claims[0].text + ' '
    equivalent = review(edits=[{'claim_id': proposed.claims[0].claim_id,
        'change_kind': 'unchanged_meaning', 'reason': 'Only trailing whitespace changed; proposition and conditions are identical.'}])
    engine = CheckpointEngine(store, {'science.review': equivalent})
    card, _ = await review_and_revise(engine, run.run_id, 'science', original=original, proposed=proposed)
    assert engine.invocations == ['science.review']
    assert card.draft.claims[0].version == 1
    assert card.draft.claims[0].evidence_ids == ['ev_synthetic']
    assert store.get_record('ev_synthetic')['claim_version'] == 1


@pytest.mark.asyncio
async def test_accepted_support_scope_and_result_survive_post_card_commit_interruption(tmp_path, monkeypatch):
    store, run, original, proposed, initial = local_change(tmp_path)
    engine = SupportEngine(store, {'science.review': initial, 'science.support_review': review()})
    real_save = store.save_card

    def fail_after_support_save(*args, **kwargs):
        card = real_save(*args, **kwargs)
        if str(kwargs.get('creation_key', '')).endswith('.support.card'):
            monkeypatch.setattr(store, 'save_card', real_save)
            raise InterruptedError('Support accepted and card saved before cycle checkpoint')
        return card

    monkeypatch.setattr(store, 'save_card', fail_after_support_save)
    with pytest.raises(InterruptedError):
        await review_and_revise(engine, run.run_id, 'science', original=original, proposed=proposed)
    frozen = deepcopy(store.get_run(run.run_id).state['task_inputs']['science.support_review'])
    accepted = store.get_task(run.run_id + '.science.support_review')
    before = list(engine.invocations)
    cards = store.list_cards(run_id=run.run_id)
    card, result = await review_and_revise(engine, run.run_id, 'science')
    assert result.action == 'retain' and card.version == 3
    assert engine.invocations == before
    assert store.get_task(accepted.task_id) == accepted
    assert store.get_run(run.run_id).state['task_inputs']['science.support_review'] == frozen
    assert store.list_cards(run_id=run.run_id) == cards


@pytest.mark.asyncio
@pytest.mark.parametrize('counting_error', [False, True])
async def test_scope_keeps_tools_and_allows_related_new_error(tmp_path, counting_error):
    store, run, original, proposed, initial = local_change(tmp_path, counting_error=counting_error)
    location = '/resources/workload_assumptions/data_amount' if counting_error else '/claims/1/text'
    quote = proposed.resources.workload_assumptions.data_amount if counting_error else proposed.claims[1].text
    finding = defect(location=location, quoted_text=quote,
        severity='missing_evidence', reason='The replacement source only reports joint change, so this dependent isolation claim is unestablished.',
        consequence='The unchanged hypothesis still needs a discriminating test.')
    if counting_error:
        finding.reason = 'The support-dependent protocol lists four 20K conditions; the resource total must be 80K rather than 100K.'
        finding.consequence = 'The experiment resource estimate counts an absent fifth condition.'
    unresolved = review('needs_evidence', findings=[finding])

    class ScopeEngine(SupportEngine):
        async def call(self, *args, **kwargs):
            if args[1] == 'science.support_review':
                assert kwargs['tool_profile'] == ['read_record', 'search_web']
            return await super().call(*args, **kwargs)

    engine = ScopeEngine(store, {'science.review': initial, 'science.support_review': unresolved})
    card, result = await review_and_revise(engine, run.run_id, 'science', original=original,
        proposed=proposed, tool_profile=['read_record', 'search_web'])
    assert result.action == 'needs_evidence'
    assert result.decisive_findings[0].location == location
    assert card.draft.claims[1] == original.draft.claims[1]
    assert result.decisive_findings[0].reason == finding.reason
