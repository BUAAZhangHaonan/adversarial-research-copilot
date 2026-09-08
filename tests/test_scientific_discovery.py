"""Default discovery quota and persistence boundaries, with real Store state."""
import pytest

from arc.schemas import ConceptionResult
from arc.scientific import discover
from tests.test_scientific_cycle import CheckpointEngine, review
from tests.test_selection import research_draft, research_store


def discovery_run(tmp_path, *, max_draws=5, shared=True):
    store, _, evidence = research_store(tmp_path)
    campaign = store.create_campaign('Separate distance and interference.',
        ['Keep equal budget'], max_draws=max_draws)
    run = store.create_run('discover', campaign_id=campaign.campaign_id,
        state={'evidence_ids': [evidence.evidence_id]} if shared else {})
    return store, campaign, run, evidence


def conception(*, candidate=None, stop=False):
    return ConceptionResult(card_candidate=candidate,
        continue_or_stop='STOP' if stop else 'CONTINUE',
        composition_reason='No worthwhile distinct insight.' if candidate is None
            else 'Separate interventions can justify different remedies.',
        distinct_from_retained='No retained candidate has this intervention comparison.')


@pytest.mark.asyncio
async def test_five_null_candidates_consume_five_opportunities_without_creating_cards(tmp_path):
    store, campaign, run, _ = discovery_run(tmp_path)
    keys = [f'draw{number}.conception' for number in range(1, 6)]
    engine = CheckpointEngine(store, {key: conception() for key in keys})
    await discover(engine, run.run_id)
    final = store.get_run(run.run_id)
    assert final.status == 'COMPLETED' and final.stop_reason == 'draw_limit_reached'
    assert store.get_campaign(campaign.campaign_id).draws_started == 5
    assert len(final.state['draws']) == 5
    assert all(item['finished'] for item in final.state['draws'].values())
    assert store.list_cards(run_id=run.run_id) == []
    assert engine.invocations == keys
    assert [engine.payloads[key]['opportunities_remaining'] for key in keys] == [5, 4, 3, 2, 1]
    await discover(engine, run.run_id)
    assert engine.invocations == keys
    assert store.get_campaign(campaign.campaign_id).draws_started == 5


@pytest.mark.asyncio
async def test_stop_ends_discovery_early_and_resume_does_not_start_another_draw(tmp_path):
    store, campaign, run, _ = discovery_run(tmp_path)
    engine = CheckpointEngine(store, {'draw1.conception': conception(),
                                     'draw2.conception': conception(stop=True)})
    await discover(engine, run.run_id)
    final = store.get_run(run.run_id)
    assert final.status == 'COMPLETED' and final.stop_reason == 'no_worthwhile_distinct_insight'
    assert final.state['scientific_stop_reason'] == 'No worthwhile distinct insight.'
    assert store.get_campaign(campaign.campaign_id).draws_started == 2
    assert engine.invocations == ['draw1.conception', 'draw2.conception']
    await discover(engine, run.run_id)
    assert engine.invocations == ['draw1.conception', 'draw2.conception']
    assert store.get_campaign(campaign.campaign_id).draws_started == 2


@pytest.mark.asyncio
async def test_supplied_shared_material_reaches_conception_without_mandatory_investigation(tmp_path):
    store, _, run, evidence = discovery_run(tmp_path, max_draws=1)
    # CheckpointEngine.investigate raises, making an unsolicited investigation fail.
    engine = CheckpointEngine(store, {'draw1.conception': conception()})
    await discover(engine, run.run_id)
    assert engine.invocations == ['draw1.conception']
    assert store.get_run(run.run_id).state['evidence_ids'] == [evidence.evidence_id]
    assert store.list_evidence(run_id=run.run_id) == []
    assert engine.payloads['draw1.conception']['evidence'][0]['evidence_id'] == evidence.evidence_id


@pytest.mark.asyncio
async def test_pre_admission_failure_preserves_quota_and_successful_shared_work_on_resume(tmp_path, monkeypatch):
    store, campaign, run, evidence = discovery_run(tmp_path, max_draws=1, shared=False)

    class SharedEngine(CheckpointEngine):
        investigations = 0

        async def investigate(self, run_id, key, questions, **kwargs):
            self.investigations += 1
            assert key == 'shared_investigation' and questions == [campaign.topic]
            self.checkpoint(run_id, evidence_ids=[evidence.evidence_id],
                            shared_investigation={'completed': True})

    engine = SharedEngine(store, {'draw1.conception': conception(candidate=research_draft()),
        'draw1.science.review': review()}, interrupt_before='draw1.conception')
    with pytest.raises(InterruptedError):
        await discover(engine, run.run_id)
    assert engine.investigations == 1 and engine.invocations == []
    assert store.get_campaign(campaign.campaign_id).draws_started == 0
    assert store.list_cards(run_id=run.run_id) == []

    real_save = store.save_card

    def interrupt_card_save(*args, **kwargs):
        monkeypatch.setattr(store, 'save_card', real_save)
        raise InterruptedError('Response accepted, card not yet persisted')

    monkeypatch.setattr(store, 'save_card', interrupt_card_save)
    with pytest.raises(InterruptedError):
        await discover(engine, run.run_id)
    assert store.get_campaign(campaign.campaign_id).draws_started == 1
    assert engine.invocations == ['draw1.conception']
    assert store.list_cards(run_id=run.run_id) == []
    await discover(engine, run.run_id)
    assert engine.investigations == 1
    assert engine.invocations == ['draw1.conception', 'draw1.science.review']
    assert store.get_campaign(campaign.campaign_id).draws_started == 1
    assert store.get_run(run.run_id).status == 'COMPLETED'
    assert len(store.list_cards(run_id=run.run_id)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary', ['selection_persisted', 'draw_finished_persisted'])
async def test_final_selection_and_finished_checkpoint_resume_without_repeated_model_calls(tmp_path, monkeypatch, boundary):
    store, campaign, run, _ = discovery_run(tmp_path, max_draws=1)
    engine = CheckpointEngine(store, {'draw1.conception': conception(candidate=research_draft()),
                                     'draw1.science.review': review()})
    if boundary == 'selection_persisted':
        original = store.record_selection

        def interrupted_selection(*args, **kwargs):
            original(*args, **kwargs)
            monkeypatch.setattr(store, 'record_selection', original)
            raise InterruptedError('Selection persisted before draw completion')

        monkeypatch.setattr(store, 'record_selection', interrupted_selection)
    else:
        original = engine.checkpoint

        def interrupted_checkpoint(run_id, **updates):
            result = original(run_id, **updates)
            if any(item.get('finished') for item in updates.get('draws', {}).values()):
                monkeypatch.setattr(engine, 'checkpoint', original)
                raise InterruptedError('Finished draw persisted before run completion')
            return result

        monkeypatch.setattr(engine, 'checkpoint', interrupted_checkpoint)
    with pytest.raises(InterruptedError):
        await discover(engine, run.run_id)
    card = store.list_cards(run_id=run.run_id)[0]
    assert card.selection == 'MAIN_REPORT' and card.selection_result.action == 'retain'
    assert store.get_run(run.run_id).status != 'COMPLETED'
    accepted_tasks = store.list_tasks(run.run_id)
    before = list(engine.invocations)
    await discover(engine, run.run_id)
    final = store.get_run(run.run_id)
    assert final.status == 'COMPLETED' and final.card_id is None
    assert engine.invocations == before == ['draw1.conception', 'draw1.science.review']
    assert store.list_tasks(run.run_id) == accepted_tasks
    assert store.list_cards(run_id=run.run_id) == [card]
    assert store.get_campaign(campaign.campaign_id).draws_started == 1
    draw = final.state['draws'][f'{campaign.campaign_id}.draw1']
    assert draw['finished'] and draw['card_id'] == card.card_id
    assert draw['card_version'] == card.version
    assert draw['selection']['selection'] == card.selection
    assert draw['scientific_review'] == card.selection_result.model_dump(mode='json')
