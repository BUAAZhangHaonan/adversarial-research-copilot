"""Structural evidence gates, never keyword-based scientific scoring."""
import json

from pydantic import ValidationError

from .schemas import LibrarianResult, SelectorResult, DeveloperResult, ModeratorResult, ProposerResult, SkepticResult, Envelope, CardDraft


class ProtocolViolation(ValueError):
    """A typed response violates a cross-record research contract."""


def output_validation_errors(raw: str, envelope_type, original_error: ValidationError) -> list[dict]:
    """Augment syntax feedback with strict prefix diagnostics, never parsed output."""
    errors = original_error.errors(include_url=False, include_input=False)
    if not any(error['type'] == 'json_invalid' for error in errors):
        return errors

    def reject_constant(_value):
        raise ValueError('non_json_numeric_constant')

    start = len(raw) - len(raw.lstrip(' \t\r\n'))
    try:
        prefix, end = json.JSONDecoder(parse_constant=reject_constant).raw_decode(raw, start)
    except (ValueError, RecursionError):
        return errors
    if not isinstance(prefix, dict) or not raw[end:].strip(' \t\r\n'):
        return errors
    try:
        envelope_type.model_validate(prefix)
    except ValidationError as prefix_error:
        errors.extend({**error, 'diagnostic_source': 'complete_json_prefix',
                       'diagnostic_range': {'start': start, 'end': end, 'unit': 'unicode_codepoints'},
                       'feedback_only': True}
                      for error in prefix_error.errors(include_url=False, include_input=False))
    return errors


PROPOSED_ISSUE_VERSION_CONTRACT = 'same_round_new_issues_target_proposed_revision_v1'


def claim_edit_assessments(original, draft, assessments, *, require_complete=False):
    """Validate explicit review coverage; never infer meaning from string edits."""
    old = {c.claim_id: c for c in original.draft.claims}
    new = {c.claim_id: c for c in draft.claims}
    changed = {key for key in old.keys() | new.keys() if key not in old or key not in new
               or any(getattr(old[key], field) != getattr(new[key], field)
                      for field in ('text', 'conditions', 'kind'))}
    reviews = {}
    for item in assessments:
        item = item.model_dump(mode='json') if hasattr(item, 'model_dump') else dict(item)
        key = item.get('claim_id')
        if (key in reviews or key not in old.keys() | new.keys()
                or item.get('change_kind') not in {'unchanged_meaning', 'substantive'}
                or not isinstance(item.get('reason'), str) or not item['reason'].strip()):
            raise ProtocolViolation('CLAIM_EDIT_REVIEW_INVALID')
        if item['change_kind'] == 'unchanged_meaning' and (
                key not in old or key not in new or old[key].kind != new[key].kind):
            raise ProtocolViolation('CLAIM_EDIT_EQUIVALENCE_CANNOT_CHANGE_IDENTITY_OR_KIND')
        reviews[key] = item
    if require_complete and not changed <= reviews.keys():
        raise ProtocolViolation('CLAIM_EDIT_REVIEW_COVERAGE')
    return reviews


def derive_claim_versions(original, result, *, prior_issues=(), new_issue_contract=False, edit_assessments=()):
    """Assign omitted increments in a copy; never transfer evidence or judgments."""
    if isinstance(result, DeveloperResult):
        field = 'proposed_revision'
    elif isinstance(result, ModeratorResult):
        field = 'proposed_card_revision'
    elif isinstance(result, CardDraft):
        field = None
    else:
        raise TypeError('claim_version_derivation_requires_revision_result')
    derived = result.model_copy(deep=True)
    draft = getattr(derived, field) if field else derived
    changes, references = [], []
    if draft is None:
        return derived, changes, references
    old = {claim.claim_id: claim for claim in original.draft.claims}
    reviews = claim_edit_assessments(original, draft, edit_assessments,
                                    require_complete=bool(edit_assessments))
    for claim in draft.claims:
        previous = old.get(claim.claim_id)
        if previous is None:
            continue
        changed_fields = [name for name in ('text', 'conditions', 'kind')
                          if getattr(previous, name) != getattr(claim, name)]
        review = reviews.get(claim.claim_id)
        if review and changed_fields:
            effective = previous.version + (review['change_kind'] == 'substantive')
            changes.append({'claim_id': claim.claim_id, 'original_version': previous.version,
                            'submitted_version': claim.version, 'effective_version': effective,
                            'changed_fields': changed_fields, **review})
            claim.version = effective
        # Without a reviewed classification retain the conservative old rule.
        elif changed_fields and claim.version == previous.version:
            changes.append({'claim_id': claim.claim_id, 'original_version': previous.version,
                            'submitted_version': claim.version, 'effective_version': previous.version + 1,
                            'changed_fields': changed_fields})
            claim.version = previous.version + 1
    by_id = {change['claim_id']: change for change in changes}

    def update(reference, path):
        change = by_id.get(reference.claim_id)
        if change and reference.claim_version == change['submitted_version']:
            reference.claim_version = change['effective_version']
            references.append({'path': path, 'claim_id': reference.claim_id,
                               'submitted_version': change['submitted_version'],
                               'effective_version': change['effective_version']})

    if isinstance(derived, DeveloperResult):
        for index, review in enumerate(derived.evidence_review):
            update(review, f'evidence_review.{index}.claim_version')
    elif isinstance(derived, ModeratorResult):
        existing = {issue['issue_id'] if isinstance(issue, dict) else issue.issue_id
                    for issue in prior_issues}
        for index, issue in enumerate(derived.updated_issues):
            change = by_id.get(issue.claim_id)
            if (issue.issue_id not in existing and change
                    and issue.claim_version == change['submitted_version']):
                if not new_issue_contract:
                    raise ProtocolViolation('CLAIM_VERSION_ISSUE_TARGET_AMBIGUOUS')
                update(issue, f'updated_issues.{index}.claim_version')
    return derived, changes, references


def remove_superseded_claim_evidence(store, result):
    """Remove earlier same-claim targets in a copy, without rebinding evidence."""
    derived = result.model_copy(deep=True)
    draft = (derived if isinstance(derived, CardDraft) else derived.proposed_revision
             if isinstance(derived, DeveloperResult) else derived.proposed_card_revision)
    removed = []
    if draft is None:
        return derived, removed
    evidence = {item.evidence_id: item for item in store.list_evidence(
        ids=sorted({eid for claim in draft.claims for eid in claim.evidence_ids}))}
    for claim in draft.claims:
        retained = []
        for evidence_id in claim.evidence_ids:
            item = evidence.get(evidence_id)
            if item is not None and item.claim_id == claim.claim_id and item.claim_version < claim.version:
                removed.append({'claim_id': claim.claim_id, 'claim_version': claim.version,
                                'evidence_id': evidence_id, 'evidence_claim_version': item.claim_version,
                                'source_id': item.source_id,
                                'evidence_verification_status': item.verification_status,
                                'reason': 'superseded_same_claim_target'})
            else:
                # Unknown IDs, future versions and other-claim background references
                # remain subject to the existing strict Store validation.
                retained.append(evidence_id)
        claim.evidence_ids = retained
    return derived, removed


def validate_role_targets(envelope: Envelope, payload: dict) -> None:
    """Check explicit role IDs against the frozen card and issue ledger only."""
    result = envelope.result
    if not isinstance(result, (ProposerResult, SkepticResult)):
        return
    card = payload.get('card')
    if card is not None and (card.get('card_id'), card.get('version')) != (
        envelope.subject.card_id, envelope.subject.card_version
    ):
        raise ProtocolViolation('ROLE_TARGET_CARD_SUBJECT_MISMATCH')
    claims = {claim['claim_id'] for claim in card['draft']['claims']} if card else set()
    supplied_issues = payload.get('issues', [])
    issues = {issue['issue_id']: issue for issue in supplied_issues}
    if len(issues) != len(supplied_issues):
        raise ProtocolViolation('ROLE_TARGET_DUPLICATE_ISSUE_ID')
    if isinstance(result, ProposerResult):
        # claims_defended/narrowed/withdrawn are prose, not ID fields.
        for response in result.issue_responses:
            if response.issue_id not in issues:
                raise ProtocolViolation('PROPOSER_ISSUE_NOT_IN_CURRENT_LEDGER')
    else:
        for criticism in result.criticisms:
            if criticism.issue_id is not None:
                issue = issues.get(criticism.issue_id)
                if issue is None:
                    raise ProtocolViolation('SKEPTIC_ISSUE_NOT_IN_CURRENT_LEDGER')
                if criticism.claim_id != issue['claim_id']:
                    raise ProtocolViolation('SKEPTIC_ISSUE_CLAIM_MISMATCH')
            elif criticism.claim_id not in claims:
                raise ProtocolViolation('SKEPTIC_CLAIM_NOT_IN_CURRENT_CARD')


def validate_archive_comparisons(result: LibrarianResult, records, store=None):
    expected = {(r['card_id'], r['version']) for r in records}
    actual = [(r.archive_card_id, r.archive_card_version) for r in result.comparisons]
    missing = sorted(expected - set(actual))
    duplicates = [{'loc': ['result', 'comparisons', index], 'card_id': key[0], 'version': key[1]}
                  for index, key in enumerate(actual) if key in actual[:index]]
    if missing or duplicates:
        raise ProtocolViolation('ARCHIVE_COMPARISON_COVERAGE; ' + json.dumps({
            'loc': ['result', 'comparisons'],
            'missing': [{'card_id': key[0], 'version': key[1]} for key in missing],
            'duplicates': duplicates}, ensure_ascii=False))
    by_id = {(r['card_id'], r['version']): r for r in records}
    cards = {}
    if store is not None:
        from .store import StateError
        for index, key in enumerate(actual):
            try:
                cards[key] = store.get_card(*key)
            except StateError as exc:
                if str(exc) != 'card_missing':
                    raise
                raise ProtocolViolation('ARCHIVE_COMPARISON_UNKNOWN_CARD; ' + json.dumps({
                    'loc': ['result', 'comparisons', index], 'card_id': key[0], 'version': key[1]})) from exc
    elif set(actual) - expected:
        raise ProtocolViolation('ADDITIONAL_ARCHIVE_COMPARISONS_REQUIRE_REGISTRY')
    for index, relation in enumerate(result.comparisons):
        if relation.relation != 'reopening_candidate' or not relation.reopening_condition_met:
            continue
        key = (relation.archive_card_id, relation.archive_card_version)
        conditions = cards[key].draft.risks.reopen_conditions if store is not None else by_id[key]['reopen_conditions']
        if relation.reopening_condition not in conditions:
            raise ProtocolViolation('REOPENING_CONDITION_NOT_RECORDED; ' + json.dumps({
                'loc': ['result', 'comparisons', index, 'reopening_condition'], 'recorded_conditions': conditions}))
        if store is None:
            raise ProtocolViolation('REOPENING_REQUIRES_REGISTRY')
        try:
            store.validate_references(relation)
        except StateError as exc:
            raise ProtocolViolation(str(exc) + '; loc=result.comparisons.' + str(index) + '.new_evidence_ids') from exc
        old_card = cards[key]
        old_evidence = set(old_card.draft.motivation.evidence_ids)
        for claim in old_card.draft.claims:
            old_evidence.update(claim.evidence_ids)
        if not set(relation.new_evidence_ids) - old_evidence:
            raise ProtocolViolation('REOPENING_REQUIRES_NEW_EVIDENCE; loc=result.comparisons.' + str(index) + '.new_evidence_ids')


def validate_evaluator_coverage(result, candidates):
    """Require one addressed finding per presented candidate, not a ranking."""
    expected = {item['candidate_id'] for item in candidates}
    supplied = [item.candidate_id for item in result.per_candidate_findings]
    duplicates = sorted({identifier for index, identifier in enumerate(supplied)
                         if identifier in supplied[:index]})
    if duplicates or set(supplied) != expected:
        raise ProtocolViolation('EVALUATOR_CANDIDATE_COVERAGE; ' + json.dumps({
            'loc': ['result', 'per_candidate_findings'], 'expected': sorted(expected),
            'supplied': supplied, 'missing': sorted(expected - set(supplied)),
            'duplicate': duplicates, 'unknown': sorted(set(supplied) - expected)}, ensure_ascii=False))


def validate_selection(store, card, judgment: SelectorResult, novelty, *, check_references=True):
    """Report independent selection prerequisites without changing scientific labels."""
    from .store import StateError
    if check_references:
        store.validate_references(judgment.model_dump(mode='json'))
        store.validate_references(novelty.model_dump(mode='json'))
    errors = []

    def reject(code, loc, **details):
        errors.append({'type': code, 'loc': loc, **details})

    def evidence_record(identifier):
        try:
            return store.get_record(identifier)
        except StateError:
            # Runtime diagnoses addresses independently. An unavailable address
            # cannot establish any of the scientific prerequisites below.
            return {}

    checks = judgment.selection_checks
    if judgment.selection == 'MAIN_REPORT':
        for name in ('motivation', 'knowledge_delta', 'test_identifiability', 'resource_path', 'stitching'):
            check = getattr(checks, name)
            allowed = ['supported', 'not_applicable'] if name == 'stitching' else ['supported']
            if check.status not in allowed:
                reject('MAIN_REPORT_PREREQUISITE_UNESTABLISHED',
                    ['result', 'selection_checks', name, 'status'],
                    supplied=check.status, expected=allowed, selection=judgment.selection)
            if not check.rationale:
                reject('MAIN_REPORT_RATIONALE_REQUIRED', ['result', 'selection_checks', name, 'rationale'])
        if novelty.contribution_coverage in ('covered', 'unknown'):
            reject('MAIN_REPORT_COVERAGE_UNESTABLISHED', ['payload', 'novelty', 'contribution_coverage'],
                supplied=novelty.contribution_coverage, expected=['not_covered', 'partial'])
        if not card.draft.motivation.evidence_ids:
            reject('MAIN_REPORT_MOTIVATION_EVIDENCE_REQUIRED', ['payload', 'card', 'draft', 'motivation', 'evidence_ids'])
        if not any(evidence_record(e).get('verification_status') == 'verified'
                   for e in card.draft.motivation.evidence_ids):
            reject('MAIN_REPORT_UNVERIFIED_MOTIVATION', ['payload', 'card', 'draft', 'motivation', 'evidence_ids'])
        if judgment.stitching_type == 'unsupported_stitching':
            reject('MAIN_REPORT_UNSUPPORTED_STITCHING', ['result', 'stitching_type'])
        if judgment.stitching_type == 'combination_exception':
            for name in ('meaningful_gain_basis', 'interaction_prediction', 'matched_budget_test'):
                if not getattr(judgment, name):
                    reject('COMBINATION_EXCEPTION_INCOMPLETE', ['result', name])
    if novelty.contribution_coverage == 'covered':
        covered = [(index, work) for index, work in enumerate(novelty.closest_works) if work.coverage == 'covered']
        if not covered:
            reject('COVERAGE_REQUIRES_SPECIFIC_EVIDENCE', ['payload', 'novelty', 'closest_works'])
        for index, work in covered:
            if not all((work.evidence_ids, work.established_claim, work.card_claim, work.rationale)):
                reject('COVERAGE_REQUIRES_SPECIFIC_EVIDENCE', ['payload', 'novelty', 'closest_works', index])
            for ei, evidence_id in enumerate(work.evidence_ids):
                evidence = evidence_record(evidence_id)
                loc = ['payload', 'novelty', 'closest_works', index, 'evidence_ids', ei]
                if evidence.get('source_id') != work.source_id:
                    reject('COVERAGE_EVIDENCE_SOURCE_MISMATCH', loc, supplied=evidence_id)
                if evidence.get('verification_status') != 'verified':
                    reject('COVERAGE_EVIDENCE_UNVERIFIED', loc, supplied=evidence_id)
    if errors:
        raise ProtocolViolation(json.dumps(errors, ensure_ascii=False))


def validate_revision(store, original, revision: DeveloperResult, *, edit_assessments=(), review_task_id=None):
    if revision.unchanged_problem_anchor != original.draft.problem_anchor:
        raise ProtocolViolation('ORIGINAL_ANCHOR_CHANGED')
    if revision.proposed_revision is None:
        return
    old = {c.claim_id: c for c in original.draft.claims}
    new = {c.claim_id: c for c in revision.proposed_revision.claims}
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    if set(revision.affected_claims) != changed:
        raise ProtocolViolation('AFFECTED_CLAIMS_COVERAGE')
    reviews = {r.claim_id: r for r in revision.evidence_review}
    if len(reviews) != len(revision.evidence_review) or not changed.issubset(reviews):
        raise ProtocolViolation('CLAIM_REVIEW_COVERAGE')
    for claim_id in old.keys() - new.keys():
        review = reviews[claim_id]
        if review.claim_version != old[claim_id].version or not review.explanation.strip():
            raise ProtocolViolation('DELETED_CLAIM_REVIEW_VERSION_OR_EXPLANATION')
    for claim_id in changed & new.keys():
        review = reviews[claim_id]
        if review.claim_version != new[claim_id].version or not review.explanation:
            raise ProtocolViolation('CLAIM_REVIEW_VERSION')
        if new[claim_id].evidence_ids and not review.still_applicable:
            raise ProtocolViolation('REVISED_CLAIM_INHERITS_INVALID_EVIDENCE')
    store.validate_claim_dependencies(original, revision.proposed_revision,
        edit_assessments=edit_assessments,review_task_id=review_task_id)
