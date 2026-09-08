"""Natural-stage preparation keeps material provenance and explicit selection."""
import importlib.util
from pathlib import Path

import pytest

from arc.budget import BudgetLedger
from arc.config import Settings
from arc.store import StateError
from tests.test_selection import research_store, research_draft
from tests.test_scientific_cycle import review

spec = importlib.util.spec_from_file_location('natural_launcher', Path(__file__).parents[1] / 'scripts/start_natural_validation.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def environment(tmp_path, monkeypatch):
    import arc.cli
    store, source, evidence = research_store(tmp_path)
    ledger = BudgetLedger(store.db_path)
    ledger.create_account('existing-parent', '600')
    settings = Settings(data_dir=tmp_path, draws=5)
    campaign = store.create_campaign('A new original question', boundaries=['One 3090', 'No large-model training'])
    material = store.create_run('discover', run_id='material-only', campaign_id=campaign.campaign_id,
        state={'source_ids': [source.source_id], 'evidence_ids': [evidence.evidence_id], 'material_only': True,
               'final_scientific_review': {'action': 'retain'}})
    store.update_run(material.run_id, status='COMPLETED', stop_reason='material_prepared')
    monkeypatch.setattr(arc.cli, 'services', lambda _: (store, ledger))
    monkeypatch.setattr(launcher, 'services', lambda _: (store, ledger))
    return settings, store, ledger


def test_material_preparation_is_not_a_generated_draw_or_a_completed_run(tmp_path, monkeypatch):
    settings, store, ledger = environment(tmp_path, monkeypatch)
    run = launcher.prepare_discover(settings, prefix='natural', parent='existing-parent', material_run='material-only')
    campaign = store.get_campaign(run.campaign_id)
    assert campaign.topic == 'A new original question'
    assert campaign.boundaries == ['One 3090', 'No large-model training']
    assert campaign.max_draws == 5 and campaign.draws_started == 0
    assert run.status == 'RUNNING' and run.card_id is None
    assert run.state['evidence_ids'] == ['ev_synthetic']
    assert 'final_scientific_review' not in run.state and 'material_only' not in run.state
    assert run.state['material_is_generation_result'] is False
    assert ledger.summary(run.run_id)['parent_id'] == 'existing-parent'
    assert ledger.summary(run.run_id)['limit_cny'] == '200.000000'
    assert store.list_tasks(run.run_id) == []
    with pytest.raises(StateError, match='RUN_ALREADY_EXISTS'):
        launcher.prepare_discover(settings, prefix='natural', parent='existing-parent', material_run='material-only')
    resumed = launcher.resume_stage(settings, prefix='natural', stage='discover', parent='existing-parent')
    assert resumed.run_id == run.run_id and store.get_campaign(run.campaign_id).draws_started == 0


def test_rejected_card_does_not_automatically_enter_develop(tmp_path, monkeypatch):
    settings, store, ledger = environment(tmp_path, monkeypatch)
    discover = launcher.prepare_discover(settings, prefix='natural', parent='existing-parent', material_run='material-only')
    card = store.save_card(research_draft(), creation_key='rejected', run_id=discover.run_id)
    store.record_selection(discover.run_id, card.card_id, card.version, review('reject'))
    store.update_run(discover.run_id, status='COMPLETED')
    with pytest.raises(StateError, match='REJECTED_CARD_REQUIRES_RESOLUTION'):
        launcher.prepare_selected_stage(settings, prefix='natural', stage='develop', card_id=card.card_id,
            version=card.version, selection_reason='An explicit review is still required.', parent='existing-parent')
    with pytest.raises(StateError, match='run_missing'):
        store.get_run('natural.develop')


def test_explicit_reviewed_selection_preserves_original_campaign_and_records_development_reason(tmp_path, monkeypatch):
    settings, store, ledger = environment(tmp_path, monkeypatch)
    discover = launcher.prepare_discover(settings, prefix='natural', parent='existing-parent', material_run='material-only')
    card = store.save_card(research_draft(), creation_key='retained', run_id=discover.run_id)
    store.record_selection(discover.run_id, card.card_id, card.version, review('retain'))
    store.update_run(discover.run_id, status='COMPLETED')
    developed = launcher.prepare_selected_stage(settings, prefix='natural', stage='develop', card_id=card.card_id,
        version=card.version, selection_reason='The competing predictions are worth testing.', parent='existing-parent')
    assert developed.campaign_id == discover.campaign_id
    assert developed.state['development_selection']['production_codex_in_loop'] is False
    assert developed.card_version == card.version and developed.status == 'RUNNING'
    assert store.list_tasks(developed.run_id) == []
    ledger.reserve('natural.develop', 'active-call', '1')
    with pytest.raises(StateError, match='PARENT_HAS_UNSETTLED_CALLS'):
        launcher.resume_stage(settings, prefix='natural', stage='develop', parent='existing-parent')
