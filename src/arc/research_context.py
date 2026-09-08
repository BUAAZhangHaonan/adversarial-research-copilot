"""Research inputs selected by explicit references, never by search-hit volume."""
from __future__ import annotations

from typing import Any

EVIDENCE_KEYS = {'evidence_id', 'evidence_ids', 'anchor_evidence_ids', 'trigger_evidence_ids',
                 'decisive_evidence_ids', 'basis_evidence_ids', 'new_evidence_ids'}
SOURCE_KEYS = {'source_id', 'source_ids', 'target_source_ids', 'original_sources_revisited'}


def as_data(value: Any) -> Any:
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, list):
        return [as_data(item) for item in value]
    return value


def reference_ids(value: Any, keys: set[str]) -> set[str]:
    value = as_data(value)
    if isinstance(value, list):
        return set().union(*(reference_ids(item, keys) for item in value))
    if not isinstance(value, dict):
        return set()
    found = set()
    for key, item in value.items():
        if key in keys:
            found.update(ref for ref in (item if isinstance(item, list) else [item])
                         if isinstance(ref, str))
        elif isinstance(item, (dict, list)):
            found.update(reference_ids(item, keys))
    return found


def build_research_context(store, run) -> dict:
    """Return the current question, proposal and registered working evidence.

    Only references in the card/issues and explicitly registered run findings
    select sources. Search-hit IDs remain in the run and tool traces. Evidence
    excerpts are included intact with their locators; complete records are read
    on demand. This function neither reads full source files nor mutates state.
    """
    run = as_data(run)
    state = run.get('state', {})
    card = as_data(store.get_card(run['card_id'], run['card_version'])) if run.get('card_id') else None
    issues = as_data(store.get_issues(run['run_id']))
    provenance = state.get('input_provenance') or {}
    campaign_ids = ([run['campaign_id']] if run.get('campaign_id') else
                    provenance.get('provenance_campaign_ids', []))
    campaigns = [as_data(store.get_campaign(cid)) for cid in campaign_ids]
    user_inputs = []
    for origin in [run, *[as_data(store.get_run(rid)) for rid in provenance.get('provenance_run_ids', [])]]:
        raw = origin.get('state', {}).get('imported_input')
        if raw and raw not in user_inputs:
            user_inputs.append(raw)
    original_task = {
        'topic': campaigns[0]['topic'] if len(campaigns) == 1 else None,
        'boundaries': campaigns[0]['boundaries'] if len(campaigns) == 1 else [],
        'campaigns': [{key: campaign[key] for key in ('campaign_id', 'topic', 'boundaries')}
                      for campaign in campaigns],
        'input_proposal': ({'card_id': provenance.get('card_id'),
                            'card_version': provenance.get('card_version'),
                            'provenance_run_ids': provenance.get('provenance_run_ids', [])}
                           if provenance else None),
        'user_inputs': user_inputs,
        'scope_origin': 'user_campaign' if campaigns else ('user_input' if user_inputs else 'input_proposal_only'),
        'proposal_details_are_user_constraints': False,
    }
    frame = state.get('frame') or {}
    mandate = frame.get('mandate')
    if mandate is None:
        # A later stage can inherit the original frame without inheriting its
        # selection or any scientific approval.
        for prior_id in provenance.get('provenance_run_ids', []):
            prior = as_data(store.get_run(prior_id))
            prior_frame = prior.get('state', {}).get('frame') or {}
            if prior_frame.get('mandate') is not None:
                mandate = prior_frame['mandate']
                break
    references = [card, issues, {'evidence_ids': state.get('evidence_ids', [])}]
    evidence = as_data(store.list_evidence(ids=sorted(reference_ids(references, EVIDENCE_KEYS))))
    source_ids = reference_ids([card, issues], SOURCE_KEYS) | {e['source_id'] for e in evidence}
    sources = as_data(store.list_sources(ids=sorted(source_ids)))
    # Hashes, raw bodies and bookkeeping do not help the scientific task.
    sources = [{key: source.get(key) for key in (
        'source_id', 'title', 'url', 'doi', 'arxiv_id', 'version', 'source_type',
        'access_status', 'content_origin', 'content_complete', 'content_total_chars')}
        for source in sources]
    evidence = [{key: value for key, value in item.items()
                 if key not in {'target_claim_fingerprint', 'created_at'}} for item in evidence]
    return {
        'subject': {key: run.get(key) for key in ('campaign_id', 'run_id', 'card_id', 'card_version')},
        'original_task': original_task, 'mandate': mandate,
        'card': card, 'issues': issues,
        'claim_evidence_bindings': store.claim_evidence_bindings(card['draft']) if card else [],
        'evidence': evidence, 'sources': sources,
        'provenance_verification': {
            'verified_means': 'The original excerpt is locatable in the recorded source.',
            'semantic_support_verified': False,
            'required_review': 'Check method, setting, numbers, denominator and inference against the current claim.',
            'full_source_access': 'Use read_record with source_id; excerpts retain their locator and conditions.',
        },
        'constraints': run.get('config', {}).get('constraints', {}),
        'input_provenance': {key: value for key, value in provenance.items() if key != 'source_ids'} or None,
        'claim_evidence_reselection': state.get('claim_evidence_removals', {}),
    }
