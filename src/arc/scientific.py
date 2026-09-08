"""Scientific review and one targeted revision, sharing ordinary runtime checkpoints."""
from __future__ import annotations

import json
from .schemas import CardDraft, ScientificReview, ScientificRevision
from .validation import ProtocolViolation, derive_claim_versions, remove_superseded_claim_evidence


def apply_scientific_revision(original, revision: ScientificRevision):
    draft = original.draft if hasattr(original, 'draft') else original
    candidate = draft.model_dump(mode='json')
    if revision.abandon:
        return None
    if not revision.section_updates and not revision.claim_updates and not revision.remove_claim_ids:
        raise ProtocolViolation('SCIENTIFIC_REVISION_HAS_NO_CHANGE')
    for update in revision.section_updates:
        candidate[update.field] = update.model_dump(mode='json')['value']
    claims = {item['claim_id']: item for item in candidate['claims']}
    for claim_id in revision.remove_claim_ids:
        if claim_id not in claims:
            raise ProtocolViolation('SCIENTIFIC_REVISION_REMOVES_UNKNOWN_CLAIM')
        del claims[claim_id]
    for item in revision.claim_updates:
        claims[item.claim_id] = item.model_dump(mode='json')
    candidate['claims'] = list(claims.values())
    candidate = CardDraft.model_validate(candidate)
    if candidate == draft:
        raise ProtocolViolation('SCIENTIFIC_REVISION_HAS_NO_CHANGE')
    return candidate


def pointer_value(body, pointer):
    if not pointer.startswith('/'):
        raise ProtocolViolation('SCIENTIFIC_FINDING_REQUIRES_JSON_POINTER')
    target = body
    try:
        for part in pointer[1:].split('/'):
            part = part.replace('~1', '/').replace('~0', '~')
            if isinstance(target, list):
                if not part.isascii() or not part.isdecimal() or (len(part) > 1 and part[0] == '0'):
                    raise ValueError('invalid array index')
                target = target[int(part)]
            else:
                target = target[part]
    except (KeyError, ValueError, IndexError, TypeError) as exc:
        raise ProtocolViolation('SCIENTIFIC_FINDING_LOCATION_NOT_IN_CARD') from exc
    return target


def validate_scientific_review(store, draft, review: ScientificReview, *, previous=None, previous_draft=None):
    """Check that the actual review refers to this draft; do not decide scientific truth in code."""
    store.validate_references(review)
    body = draft.model_dump(mode='json')
    for finding in review.decisive_findings:
        target = pointer_value(body, finding.location)
        target_text = target if isinstance(target, str) else json.dumps(target, ensure_ascii=False)
        if finding.quoted_text and finding.quoted_text not in target_text:
            raise ProtocolViolation('SCIENTIFIC_FINDING_QUOTE_NOT_AT_LOCATION')
    expected = {f.finding_id for f in previous.decisive_findings} if previous else set()
    supplied = [f.finding_id for f in review.prior_findings]
    if set(supplied) != expected:
        raise ProtocolViolation('SCIENTIFIC_RECHECK_MUST_ADDRESS_PREVIOUS_FINDINGS; '
            'expected_previous_decisive_ids=' + json.dumps(sorted(expected)) +
            '; supplied_prior_ids=' + json.dumps(supplied))
    if previous_draft is not None:
        statuses = {f.finding_id: f.status for f in review.prior_findings}
        old_body = previous_draft.model_dump(mode='json')
        for finding in previous.decisive_findings:
            if statuses[finding.finding_id] != 'resolved':
                continue
            old_value = pointer_value(old_body, finding.location)
            try:
                new_value = pointer_value(body, finding.location)
            except ProtocolViolation:
                continue  # Removing the faulty claim is a legitimate revision.
            if old_value == new_value:
                raise ProtocolViolation('SCIENTIFIC_REPAIR_LEFT_FAULTY_FIELD_UNCHANGED')
    for work in review.verification_work:
        if work.method == 'source_read' and not (work.evidence_ids or work.source_ids):
            raise ProtocolViolation('SCIENTIFIC_SOURCE_REVIEW_REQUIRES_REFERENCE')
    return review


def validate_scientific_output_contract(store, payload, result):
    """Validate output addressing/coverage before the existing JSON repair gate.

    This never classifies a claim's meaning or checks whether a scientific
    objection is true. Those decisions remain explicit model outputs and the
    independent revision/recheck cycle.
    """
    if isinstance(result, ScientificRevision):
        target = CardDraft.model_validate(payload['review_target'])
        # Parse every typed section and check update/removal addressing. This
        # only validates the proposed shape; it neither saves a card nor claims
        # the scientific defect has been fixed.
        apply_scientific_revision(target, result)
        previous = ScientificReview.model_validate(payload['scientific_review'])
        expected = {item.finding_id for item in previous.decisive_findings}
        supplied = [item.finding_id for item in result.addressed_findings]
        if len(supplied) != len(set(supplied)) or set(supplied) != expected:
            raise ProtocolViolation('SCIENTIFIC_REVISION_MUST_ADDRESS_FINDINGS; expected=' +
                json.dumps(sorted(expected)) + '; supplied=' + json.dumps(supplied))
        return
    if not isinstance(result, ScientificReview):
        return
    from .schemas import ResearchCard
    from .validation import claim_edit_assessments
    target = CardDraft.model_validate(payload['review_target'])
    previous = ScientificReview.model_validate(payload['previous_review']) if payload.get('previous_review') else None
    validate_scientific_review(store, target, result, previous=previous)
    if payload.get('original_card') and payload.get('proposed_revision'):
        original = ResearchCard.model_validate(payload['original_card'])
        proposed = CardDraft.model_validate(payload['proposed_revision'])
        try:
            claim_edit_assessments(original, proposed, result.edit_assessments, require_complete=True)
        except ProtocolViolation as exc:
            old = {item.claim_id: item for item in original.draft.claims}
            new = {item.claim_id: item for item in proposed.claims}
            changed = {cid: ['added'] if cid not in old else ['deleted'] if cid not in new else
                       [field for field in ('text', 'conditions', 'kind')
                        if getattr(old[cid], field) != getattr(new[cid], field)]
                       for cid in sorted(old.keys() | new.keys())}
            changed = {cid: fields for cid, fields in changed.items() if fields}
            supplied = [item.claim_id for item in result.edit_assessments]
            raise ProtocolViolation(str(exc) + '; changed_claims=' + json.dumps(changed, ensure_ascii=False)
                + '; supplied_claim_ids=' + json.dumps(supplied, ensure_ascii=False)
                + '; required change_kind is unchanged_meaning or substantive, with nonempty reason; '
                  'added/deleted claims cannot be unchanged_meaning') from exc


def _accepted_result_task(engine, run_id, key, result, card, role):
    """Resolve the accepted physical task, including explicit/research retries."""
    result_data = result.model_dump(mode='json')
    for task_id in reversed(engine.trace_tasks(run_id, key)):
        task = engine.store.get_task(task_id)
        accepted = task.accepted_result if task else None
        if (task is None or task.run_id != run_id or task.status != 'ACCEPTED'
                or not accepted or accepted.get('result') != result_data):
            continue
        subject = accepted.get('subject', {})
        if (subject.get('card_id'), subject.get('card_version')) != (card.card_id, card.version):
            raise ProtocolViolation('SCIENTIFIC_ACCEPTED_TASK_CARD_MISMATCH')
        snapshot = json.loads(engine.store.read_artifact(task.rendered_prompt_path)) if task.rendered_prompt_path else {}
        if snapshot.get('prompt_id') != role + '.INVOKE':
            raise ProtocolViolation('SCIENTIFIC_ACCEPTED_TASK_ROLE_MISMATCH')
        return task
    raise ProtocolViolation('SCIENTIFIC_ACCEPTED_RESULT_TASK_MISSING')


def _registered_support_findings(engine, run_id, key, result, card):
    # WorkflowEngine.investigate has already registered these findings under
    # the actual accepted task. Revalidate/read them; never register duplicates
    # under the logical key of a rejected request.
    task = _accepted_result_task(engine, run_id, key, result, card, 'investigator')
    records = engine.store.validate_findings(result.findings + result.contrary_findings,
        task_id=task.task_id, allowed_claims=card.draft.claims)
    registered = engine.store.list_evidence(ids=[record.evidence_id for record in records])
    if {record.evidence_id for record in records} != {record.evidence_id for record in registered}:
        raise ProtocolViolation('SCIENTIFIC_SUPPORT_FINDINGS_NOT_REGISTERED')
    return registered


async def review_and_revise(engine, run_id, key, *, allow_revision=True, tool_profile=None, original=None, proposed=None):
    """Initial review -> optional targeted change -> independent recheck; never refresh a draw."""
    state = engine.store.get_run(run_id).state
    saved_input = state.get('task_inputs', {}).get(key + '.review', {})
    run = engine.store.get_run(run_id)
    if saved_input:
        subject = saved_input['subject']
        frozen_original = engine.store.get_card(subject['card_id'], subject['card_version'])
        frozen_target = CardDraft.model_validate(saved_input['payload']['review_target'])
        if original is not None and (original.card_id, original.version, original.draft) != (
                frozen_original.card_id, frozen_original.version, frozen_original.draft):
            raise ProtocolViolation('SCIENTIFIC_ORIGINAL_INPUT_CHANGED')
        if proposed is not None and proposed != frozen_target:
            raise ProtocolViolation('SCIENTIFIC_PROPOSED_INPUT_CHANGED')
        original, target = frozen_original, frozen_target
        proposed = frozen_target if saved_input['payload'].get('proposed_revision') is not None else None
    else:
        original = original or engine.store.get_card(run.card_id, run.card_version)
        if (run.card_id, run.card_version) != (original.card_id, original.version):
            raise ProtocolViolation('SCIENTIFIC_INITIAL_SUBJECT_CHANGED')
        target = proposed or original.draft
    completed = state.get('scientific_cycles', {}).get(key)
    if completed:
        card = engine.store.get_card(completed['card_id'], completed['version'])
        engine.store.update_run(run_id, card_id=card.card_id, card_version=card.version)
        return card, ScientificReview.model_validate(completed['review'])
    review = await engine.call(run_id, key + '.review', 'scientific_reviewer', payload={
        **engine.context(run_id), 'original_card': original.model_dump(mode='json') if proposed else None,
        'proposed_revision': proposed.model_dump(mode='json') if proposed else None,
        'review_target': target.model_dump(mode='json'), 'previous_review': None,
    }, tool_profile=tool_profile)
    validate_scientific_review(engine.store, target, review)
    card = original
    accepted_key = key + '.review'
    revision = None
    if review.action == 'revise' and allow_revision:
        revision = await engine.call(run_id, key + '.revision', 'discovery', 'REVISE', payload={
            **engine.context(run_id), 'original_card': original.model_dump(mode='json'),
            'review_target': target.model_dump(mode='json'),
            'scientific_review': review.model_dump(mode='json'),
        }, tool_profile=tool_profile)
        if {f.finding_id for f in revision.addressed_findings} != {f.finding_id for f in review.decisive_findings}:
            raise ProtocolViolation('SCIENTIFIC_REVISION_MUST_ADDRESS_FINDINGS')
        proposed = apply_scientific_revision(target, revision)
        if proposed is not None:
            recheck_key = key + '.recheck'
            recheck = await engine.call(run_id, recheck_key, 'scientific_reviewer', payload={
                **engine.context(run_id), 'original_card': original.model_dump(mode='json'),
                'proposed_revision': proposed.model_dump(mode='json'),
                'review_target': proposed.model_dump(mode='json'),
                'previous_review': review.model_dump(mode='json'),
                'revision_summary': revision.model_dump(mode='json'),
            }, tool_profile=tool_profile)
            validate_scientific_review(engine.store, proposed, recheck, previous=review, previous_draft=target)
            target = proposed
            accepted_key = recheck_key
            review = recheck
        else:
            review = review.model_copy(update={'action': 'reject', 'value_reason': '修订者确认核心价值无法保留。' + '；'.join(revision.change_summary)})
    # No selection is silently inherited into a different scientific review.
    if target != original.draft:
        derived, _, _ = derive_claim_versions(original, target, edit_assessments=review.edit_assessments)
        derived, removed = remove_superseded_claim_evidence(engine.store, derived)
        review_task = _accepted_result_task(engine, run_id, accepted_key, review, original, 'scientific_reviewer').task_id
        card = engine.store.save_card(derived, card_id=original.card_id, parent_version=original.version,
            creation_key=f'{run_id}.{key}.science_revision.card', run_id=run_id,
            edit_assessments=review.edit_assessments, review_task_id=review_task,
            state_patch={'scientific_last_revision': revision.model_dump(mode='json') if revision else None})
        # Idempotent save_card returns early when the card already exists; put
        # the run cursor back on that reviewed version before any next task.
        engine.store.update_run(run_id, card_id=card.card_id, card_version=card.version)
        if removed:
            engine.checkpoint(run_id, **{key + '.support_removals': removed})
            evidence_key = key + '.support_recheck'
            result = await engine.investigate(run_id, evidence_key, [], fresh=False, extra={
                'verification_target': 'superseded_claim_evidence_reselection',
                'claim_evidence_recheck': {'removed_references': removed},
                'target_source_ids': sorted({item['source_id'] for item in removed}),
            })
            registered = _registered_support_findings(engine, run_id, evidence_key, result, card)
            supported = card.draft.model_copy(deep=True)
            for claim in supported.claims:
                claim.evidence_ids = sorted(set(claim.evidence_ids) | {
                    ev.evidence_id for ev in registered
                    if (ev.claim_id, ev.claim_version) == (claim.claim_id, claim.version)})
            support_key = key + '.support_review'
            affected_ids = {item['claim_id'] for item in removed}
            edit_reasons = {item.claim_id: item.reason for item in review.edit_assessments}
            affected_targets = {(claim.claim_id, claim.version) for claim in supported.claims
                if claim.claim_id in affected_ids}
            replacement_ids = {item.evidence_id for item in registered
                if (item.claim_id, item.claim_version) in affected_targets}
            original_versions = {claim.claim_id: claim.version for claim in original.draft.claims}
            support_review = await engine.call(run_id, support_key, 'scientific_reviewer', payload={
                **engine.context(run_id), 'original_card': card.model_dump(mode='json'),
                'proposed_revision': supported.model_dump(mode='json'),
                'review_target': supported.model_dump(mode='json'),
                'previous_review': review.model_dump(mode='json'),
                'support_review_scope': {
                    'kind': 'affected_support',
                    'affected_claims': [{'claim_id': claim.claim_id, 'version': claim.version,
                        'change_reason': edit_reasons.get(claim.claim_id)}
                        for claim in supported.claims if claim.claim_id in affected_ids],
                    'removed_bindings': removed,
                    'replacement_bindings': [binding for binding in engine.store.claim_evidence_bindings(supported)
                        if binding['claim_id'] in affected_ids and binding['evidence_id'] in replacement_ids],
                    'registered_evidence_ids': sorted(replacement_ids),
                    'unchanged_claim_ids': [claim.claim_id for claim in supported.claims
                        if claim.claim_id not in affected_ids and original_versions.get(claim.claim_id) == claim.version],
                    'support_recheck': result.model_dump(mode='json'),
                },
            }, tool_profile=tool_profile)
            validate_scientific_review(engine.store, supported, support_review, previous=review)
            if supported != card.draft:
                card = engine.store.save_card(supported, card_id=card.card_id, parent_version=card.version,
                    creation_key=f'{run_id}.{key}.support.card', run_id=run_id)
            review = support_review
    elif original.selection_result is not None:
        card = engine.store.save_card(original.draft, card_id=original.card_id, parent_version=original.version,
            creation_key=f'{run_id}.{key}.reviewed.card', run_id=run_id)
    engine.store.update_run(run_id, card_id=card.card_id, card_version=card.version)
    cycles = dict(engine.store.get_run(run_id).state.get('scientific_cycles', {}))
    cycles[key] = {'card_id': card.card_id, 'version': card.version, 'review': review.model_dump(mode='json')}
    engine.checkpoint(run_id, scientific_cycles=cycles)
    return card, review


async def discover(engine, run_id):
    run = engine.store.get_run(run_id)
    campaign = engine.store.get_campaign(run.campaign_id)
    if not run.state.get('evidence_ids'):
        await engine.investigate(run_id, 'shared_investigation', [campaign.topic], fresh=False,
            extra={'original_task': engine.context(run_id)['original_task']})
    for number in range(1, campaign.max_draws + 1):
        run = engine.store.get_run(run_id)
        draws = dict(run.state.get('draws', {}))
        draw_id = f'{campaign.campaign_id}.draw{number}'
        current = dict(draws.get(draw_id, {}))
        if current.get('finished'):
            engine.store.update_run(run_id, card_id=None, card_version=None)
            continue
        conception = await engine.call(run_id, f'draw{number}.conception', 'discovery', 'CONCEIVE', payload={
            **engine.context(run_id), 'previous_draws': draws, 'draw_id': draw_id,
            'opportunities_remaining': campaign.max_draws - number + 1,
        }, on_admitted=lambda: engine.store.claim_draw(campaign.campaign_id, draw_id))
        if conception.continue_or_stop == 'STOP':
            engine.checkpoint(run_id, scientific_stop_reason=conception.composition_reason)
            engine.complete(run_id, 'no_worthwhile_distinct_insight')
            return
        if conception.card_candidate is None:
            current.update(finished=True, reason=conception.composition_reason)
            draws[draw_id] = current
            engine.checkpoint(run_id, draws=draws)
            continue
        if 'card_id' not in current:
            card = engine.store.save_card(conception.card_candidate, creation_key=f'{run_id}.draw{number}.card', run_id=run_id)
            current.update(card_id=card.card_id, card_version=card.version, conception_reason=conception.composition_reason)
            draws[draw_id] = current
            engine.checkpoint(run_id, draws=draws)
        engine.store.update_run(run_id, card_id=current['card_id'], card_version=current['card_version'])
        card = engine.store.get_card(current['card_id'], current['card_version'])
        relations = await engine.archive_compare(run_id, f'draw{number}.card_archive', card.draft.problem_anchor.question,
                                                 card.model_dump(mode='json'))
        duplicate = any(r['relation'] == 'same_contribution' or (r['relation'] == 'reopening_candidate' and not r['reopening_condition_met'])
                        for r in relations.get('comparisons', []))
        if duplicate:
            current.update(finished=True, reason='historical_contribution_requires_new_evidence')
        else:
            card, review = await review_and_revise(engine, run_id, f'draw{number}.science')
            current.update(finished=True, card_version=card.version, selection={
                'selection': review.selection, 'assessment': review.assessment}, scientific_review=review.model_dump(mode='json'))
            engine.store.record_selection(run_id, card.card_id, card.version, review)
        draws = dict(engine.store.get_run(run_id).state.get('draws', {}))
        draws[draw_id] = current
        engine.checkpoint(run_id, draws=draws)
        engine.store.update_run(run_id, card_id=None, card_version=None)
    engine.complete(run_id, 'draw_limit_reached')
