from arc.research_context import build_research_context
from arc.schemas import SourceRecord, Issue
from tests.test_selection import research_store, research_draft


def test_search_hits_stay_out_of_working_materials_and_fulltext_is_on_demand(tmp_path):
    store, source, evidence = research_store(tmp_path)
    hit = store.register_source(SourceRecord(source_id='src_hit', title='A search candidate',
        url='https://example.org/hit', source_type='web_unclassified', access_status='metadata_only',
        content_origin='metadata'))
    campaign = store.create_campaign('Explain conflict under equal information', ['Must retain conflict'])
    run = store.create_run('discover', campaign_id=campaign.campaign_id,
        state={'source_ids': [hit.source_id, source.source_id], 'evidence_ids': [evidence.evidence_id]})
    before = store.get_run(run.run_id)
    context = build_research_context(store, run)
    assert context['original_task']['topic'] == campaign.topic
    assert context['original_task']['boundaries'] == campaign.boundaries
    assert [s['source_id'] for s in context['sources']] == [source.source_id]
    assert context['evidence'][0]['excerpt'] == evidence.excerpt
    assert context['evidence'][0]['locator'] == evidence.locator
    assert context['provenance_verification']['semantic_support_verified'] is False
    assert 'content_path' not in context['sources'][0]
    assert 'content_sha256' not in context['sources'][0]
    assert 'target_claim_fingerprint' not in context['evidence'][0]
    assert store.get_run(run.run_id) == before


def test_later_stage_retains_original_campaign_and_mandate_not_generated_conditions(tmp_path):
    store, source, evidence = research_store(tmp_path)
    campaign = store.create_campaign('Retain the conflict question', ['Conflict must be present'])
    origin = store.create_run('discover', campaign_id=campaign.campaign_id,
        state={'frame': {'mandate': {'question': 'The original conflict question'}}})
    card = store.save_card(research_draft(), run_id=origin.run_id)
    provenance = store.card_provenance_context(card.card_id, 1)
    run = store.create_run('run', card_id=card.card_id, card_version=1,
                           state={'input_provenance': provenance})
    context = build_research_context(store, run)
    assert context['original_task']['topic'] == campaign.topic
    assert context['original_task']['boundaries'] == campaign.boundaries
    assert context['mandate']['question'] == 'The original conflict question'
    assert context['original_task']['proposal_details_are_user_constraints'] is False
    assert 'source_ids' not in context['input_provenance']
    assert [e['evidence_id'] for e in context['evidence']] == [evidence.evidence_id]


def test_input_proposal_without_campaign_is_not_relabelled_user_scope(tmp_path):
    store, _, _ = research_store(tmp_path)
    card = store.save_card(research_draft())
    run = store.create_run('develop', card_id=card.card_id, card_version=1)
    context = build_research_context(store, run)
    assert context['original_task']['topic'] is None
    assert context['original_task']['boundaries'] == []
    assert context['original_task']['scope_origin'] == 'input_proposal_only'
    assert context['card']['draft']['problem_anchor'] == card.draft.problem_anchor.model_dump()


def test_issue_referenced_counterevidence_remains_visible_without_card_citation(tmp_path, monkeypatch):
    store, source, evidence = research_store(tmp_path)
    draft = research_draft()
    draft.motivation.evidence_ids = []
    draft.closest_work_delta.source_ids = []
    card = store.save_card(draft)
    run = store.create_run('run', card_id=card.card_id, card_version=1)
    monkeypatch.setattr(store, 'get_issues', lambda _: [Issue(issue_id='counter',
        claim_id='claim_observation', claim_version=1, content='Counterexample', status='needs_retrieval',
        evidence_ids=[evidence.evidence_id], resolution_criterion='Inspect source',
        change_this_round='New counterevidence', next_action='RETRIEVE')])
    context = build_research_context(store, run)
    assert context['evidence'][0]['evidence_id'] == evidence.evidence_id
    assert context['sources'][0]['source_id'] == source.source_id


def test_direct_user_input_survives_import_and_later_stage_provenance(tmp_path):
    store, _, _ = research_store(tmp_path)
    raw = 'Compare the two methods only on conflict examples; keep the same information.'
    origin = store.create_run('develop', state={'imported_input': raw})
    card = store.save_card(research_draft(), run_id=origin.run_id)
    direct = build_research_context(store, store.get_run(origin.run_id))
    assert direct['original_task']['user_inputs'] == [raw]
    provenance = store.card_provenance_context(card.card_id, card.version)
    later = store.create_run('run', card_id=card.card_id, card_version=card.version,
                             state={'input_provenance': provenance})
    context = build_research_context(store, later)
    assert context['original_task']['user_inputs'] == [raw]
    assert context['original_task']['scope_origin'] == 'user_input'
