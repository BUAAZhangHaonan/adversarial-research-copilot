"""Structural evidence gates, never keyword-based scientific scoring."""
from .schemas import LibrarianResult, SelectorResult, DeveloperResult


class ProtocolViolation(ValueError):
    """A typed response violates a cross-record research contract."""


def validate_archive_comparisons(result: LibrarianResult, records, store=None):
    expected = {(r['card_id'], r['version']) for r in records}
    actual = [(r.archive_card_id, r.archive_card_version) for r in result.comparisons]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ProtocolViolation('ARCHIVE_COMPARISON_COVERAGE')
    by_id = {(r['card_id'], r['version']): r for r in records}
    for relation in result.comparisons:
        if relation.relation != 'reopening_candidate' or not relation.reopening_condition_met:
            continue
        prior = by_id[(relation.archive_card_id, relation.archive_card_version)]
        if relation.reopening_condition not in prior['reopen_conditions']:
            raise ProtocolViolation('REOPENING_CONDITION_NOT_RECORDED')
        if store is None:
            raise ProtocolViolation('REOPENING_REQUIRES_REGISTRY')
        store.validate_references(relation)
        old_card = store.get_card(relation.archive_card_id, relation.archive_card_version)
        old_evidence = set(old_card.draft.motivation.evidence_ids)
        for claim in old_card.draft.claims:
            old_evidence.update(claim.evidence_ids)
        if not set(relation.new_evidence_ids) - old_evidence:
            raise ProtocolViolation('REOPENING_REQUIRES_NEW_EVIDENCE')


def validate_selection(store, card, judgment: SelectorResult, novelty):
    store.validate_references(judgment.model_dump(mode='json'))
    store.validate_references(novelty.model_dump(mode='json'))
    checks = judgment.selection_checks
    if judgment.selection == 'MAIN_REPORT':
        for name in ('motivation', 'knowledge_delta', 'test_identifiability', 'resource_path', 'stitching'):
            check = getattr(checks, name)
            if check.status != 'supported' and not (name == 'stitching' and check.status == 'not_applicable'):
                raise ProtocolViolation('MAIN_REPORT_PREREQUISITE_UNESTABLISHED')
            if not check.rationale:
                raise ProtocolViolation('MAIN_REPORT_RATIONALE_REQUIRED')
        if novelty.contribution_coverage in ('covered', 'unknown'):
            raise ProtocolViolation('MAIN_REPORT_COVERAGE_UNESTABLISHED')
        if not card.draft.motivation.evidence_ids:
            raise ProtocolViolation('MAIN_REPORT_MOTIVATION_EVIDENCE_REQUIRED')
        if not any(store.get_record(e).get('verification_status') == 'verified'
                   for e in card.draft.motivation.evidence_ids):
            raise ProtocolViolation('MAIN_REPORT_UNVERIFIED_MOTIVATION')
        if judgment.stitching_type == 'unsupported_stitching':
            raise ProtocolViolation('MAIN_REPORT_UNSUPPORTED_STITCHING')
        if judgment.stitching_type == 'combination_exception' and not all((
            judgment.meaningful_gain_basis, judgment.interaction_prediction, judgment.matched_budget_test)):
            raise ProtocolViolation('COMBINATION_EXCEPTION_INCOMPLETE')
    if novelty.contribution_coverage == 'covered':
        covered = [w for w in novelty.closest_works if w.coverage == 'covered']
        if not covered or not all(w.evidence_ids and w.established_claim and w.card_claim and w.rationale for w in covered):
            raise ProtocolViolation('COVERAGE_REQUIRES_SPECIFIC_EVIDENCE')
        for work in covered:
            for evidence_id in work.evidence_ids:
                evidence = store.get_record(evidence_id)
                if evidence.get('source_id') != work.source_id:
                    raise ProtocolViolation('COVERAGE_EVIDENCE_SOURCE_MISMATCH')
                if evidence.get('verification_status') != 'verified':
                    raise ProtocolViolation('COVERAGE_EVIDENCE_UNVERIFIED')


def validate_revision(store, original, revision: DeveloperResult):
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
    for claim_id in changed & new.keys():
        review = reviews[claim_id]
        if review.claim_version != new[claim_id].version or not review.explanation:
            raise ProtocolViolation('CLAIM_REVIEW_VERSION')
        if new[claim_id].evidence_ids and not review.still_applicable:
            raise ProtocolViolation('REVISED_CLAIM_INHERITS_INVALID_EVIDENCE')
    store.validate_claim_dependencies(original, revision.proposed_revision)
