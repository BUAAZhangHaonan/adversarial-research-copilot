"""CLI boundaries persist their effects; no model or external tools are called."""
import json
from pathlib import Path
import pytest
from typer.testing import CliRunner
from arc.cli import app, services
from arc.config import Settings, load_settings, DEFAULT_ROLES


def test_explicit_cli_options_override_config_without_default_shadowing(tmp_path, monkeypatch):
    config = tmp_path/'settings.yaml'
    config.write_text("draws: 2\nbudget_cny: '7'\nmax_rounds: 3\n", encoding='utf-8')
    async def local_only(settings, run_id):
        store, ledger = services(settings)
        run = store.get_run(run_id)
        assert run.config['draws'] == 2 and run.config['max_rounds'] == 3
        assert ledger.summary(run_id)['limit_cny'] == '7.000000'
        assert store.get_campaign(run.campaign_id).draws_started == 0
    monkeypatch.setattr('arc.cli.execute', local_only)
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path/'data'), '--config',str(config),'discover','a new question'])
    assert result.exit_code == 0, result.output + repr(result.exception)
    assert load_settings(config, draws=4).draws == 4


def test_stage_transition_not_authorized_by_default(tmp_path):
    result = CliRunner().invoke(app, ['--data-dir',str(tmp_path/'data'),'test-e2e'])
    assert result.exit_code != 0
    assert not (tmp_path/'data'/'arc.sqlite').exists()


@pytest.mark.parametrize('command',['pipeline','chat-mode'])
def test_removed_entry_points_do_not_start_work(command,tmp_path):
    result=CliRunner().invoke(app,['--data-dir',str(tmp_path/'data'),command])
    assert result.exit_code != 0
    assert not (tmp_path/'data'/'arc.sqlite').exists()


def test_user_question_import_does_not_create_campaign_or_change_topic(tmp_path,monkeypatch):
    question='The exact user question\nThe last line constrains all comparisons.'
    async def local_only(settings,run_id):
        store, ledger=services(settings)
        run=store.get_run(run_id)
        assert run.mode=='run' and run.campaign_id is None and run.card_id is None
        assert run.state['imported_input']==question
        assert store.get_record(run.state['source_ids'][0])['content']==question
        assert ledger.summary(run_id)['call_count']==0
    monkeypatch.setattr('arc.cli.execute',local_only)
    result=CliRunner().invoke(app,['--data-dir',str(tmp_path/'data'),'run','--question',question])
    assert result.exit_code==0,repr(result.exception)


def test_unknown_model_and_nonmax_effort_rejected():
    with pytest.raises(ValueError):
        Settings(roles={**DEFAULT_ROLES,'skeptic':'unknown-model'})
    with pytest.raises(ValueError):
        Settings(reasoning_effort='high')


def test_ambiguous_input_rejected_before_budget_creation(tmp_path):
    result=CliRunner().invoke(app,['--data-dir',str(tmp_path/'data'),'develop','--card','x','--question','y'])
    assert result.exit_code != 0
    assert not (tmp_path/'data'/'arc.sqlite').exists()

def test_card_stage_inherits_scoped_original_material_without_prior_approval(tmp_path, monkeypatch):
    from arc.cli import new_run
    from arc.budget import BudgetLedger
    from arc.schemas import SourceRecord
    from tests.test_selection import research_store, research_draft
    store, source, evidence = research_store(tmp_path)
    extra = store.register_source(SourceRecord(title='Unresolved original condition',
        url='https://example.org/original-condition', source_type='paper',
        access_status='retrieved', content_origin='original'),
        content='The author leaves the independence of the two controls unresolved.')
    card = store.save_card(research_draft())
    campaign = store.create_campaign('Controlled mechanisms')
    prior = store.create_run('discover', campaign_id=campaign.campaign_id,
        card_id=card.card_id, card_version=card.version,
        state={'source_ids':[source.source_id,extra.source_id], 'evidence_ids':[evidence.evidence_id]})
    store.update_run(prior.run_id, status='COMPLETED', assessment='PROMISING')
    ledger = BudgetLedger(store.db_path)
    monkeypatch.setattr('arc.cli.services', lambda settings:(store,ledger))
    stage = new_run(Settings(data_dir=tmp_path),'develop',card_id=card.card_id,version=1)
    assert stage.campaign_id == campaign.campaign_id
    assert extra.source_id in stage.state['source_ids']
    assert stage.state['input_provenance']['provenance_run_ids'] == [prior.run_id]
    assert stage.assessment is None and stage.status == 'RUNNING'
    assert 'final_ruling' not in stage.state and not store.get_issues(stage.run_id)
    assert ledger.summary(stage.run_id)['call_count'] == 0
