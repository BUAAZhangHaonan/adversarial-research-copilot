"""Complete responses can ask for further evidence without losing that handoff."""
from copy import deepcopy
import json

import pytest

from arc.config import Settings
from arc.schemas import ConceptionResult, Envelope, EvidenceRequest, TaskRecord
from arc.scientific import _evidence_handoff, discover, review_and_revise
from arc.workflows import WorkflowEngine
from tests.test_scientific_cycle import (CheckpointEngine, defect, patch, resolution,
                                         review, setup_cycle)
from tests.test_scientific_stages import ScientificStageRuntime
from tests.test_scientific_recovery import SupportEngine, setup_support
from tests.test_selection import research_draft, research_store


def request(local_id='er1', question='Does the unread section cover this remaining claim?'):
    return EvidenceRequest(request_local_id=local_id, claim_id='claim_observation',
        issue_id=None, draw_id=None, question=question,
        target_source_ids=[], queries=['nearest method remaining analysis'],
        purpose='Check the scope of the claimed difference.',
        decision_if_supported='Narrow the claimed difference.',
        decision_if_contradicted='Keep the difference with a bounded search statement.').model_dump(mode='json')


class RequestEngine(CheckpointEngine):
    def __init__(self, *args, requests=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.requests = requests or {}

    async def call(self, run_id, key, *args, **kwargs):
        result = await super().call(run_id, key, *args, **kwargs)
        if key in self.requests:
            requests = deepcopy(self.requests[key])
            self.checkpoint(run_id, **{key + '_evidence_requests': requests})
        return result


def handed_requests(payload):
    return [item['request'] for item in payload.get('evidence_request_handoff', [])]


@pytest.mark.asyncio
async def test_complete_candidate_request_reaches_review_without_other_draws_or_automatic_investigation(tmp_path):
    store, _, evidence = research_store(tmp_path)
    campaign = store.create_campaign('Separate distance and interference.', ['Equal budget'], max_draws=1)
    run = store.create_run('discover', campaign_id=campaign.campaign_id,
        state={'evidence_ids': [evidence.evidence_id], 'other_draw.conception_evidence_requests': [request('unrelated')]})
    er = request()
    engine = RequestEngine(store, {
        'draw1.conception': ConceptionResult(card_candidate=research_draft(), continue_or_stop='CONTINUE',
            composition_reason='Interventions distinguish remedies.', distinct_from_retained='First candidate.'),
        'draw1.science.review': review(),
    }, requests={'draw1.conception': [er]})
    await discover(engine, run.run_id)
    payload = engine.payloads['draw1.science.review']
    assert handed_requests(payload) == [er]
    item = payload['evidence_request_handoff'][0]
    assert item['source_task_id'] == run.run_id + '.draw1.conception'
    assert item['source_task_key'] == 'draw1.conception'
    assert 'status' not in item and 'resolved' not in item
    assert engine.invocations == ['draw1.conception', 'draw1.science.review']


@pytest.mark.asyncio
@pytest.mark.parametrize('revision_requests', [[], [request('er2')]])
async def test_recheck_keeps_initial_questions_even_when_revision_has_no_new_request(tmp_path, revision_requests):
    store, _, run, original = setup_cycle(tmp_path)
    er = request()
    engine = RequestEngine(store, {
        'science.review': review('revise', findings=[defect()]),
        'science.revision': patch(original.draft),
        'science.recheck': review('retain', resolutions=[resolution()]),
    }, requests={'science.review': [er], 'science.revision': revision_requests})
    card, result = await review_and_revise(engine, run.run_id, 'science')
    assert handed_requests(engine.payloads['science.revision']) == [er]
    assert handed_requests(engine.payloads['science.recheck']) == [er, *revision_requests]
    assert card.version == 2 and result.action == 'retain'
    # These are questions, not commands to buy evidence again or block retention.
    assert engine.invocations == ['science.review', 'science.revision', 'science.recheck']


@pytest.mark.asyncio
async def test_frozen_review_input_is_not_retroactively_rewritten_by_new_handoff(tmp_path):
    store, _, run, _ = setup_cycle(tmp_path)
    engine = RequestEngine(store, {'science.review': review()}, interrupt_before='science.review')
    with pytest.raises(InterruptedError):
        await review_and_revise(engine, run.run_id, 'science')
    frozen = deepcopy(store.get_run(run.run_id).state['task_inputs']['science.review'])
    engine.checkpoint(run.run_id, **{'conception_evidence_requests': [request()]})
    await review_and_revise(engine, run.run_id, 'science', evidence_from='conception')
    assert store.get_run(run.run_id).state['task_inputs']['science.review'] == frozen
    assert 'evidence_request_handoff' not in engine.payloads['science.review']
    assert engine.invocations == ['science.review']


@pytest.mark.asyncio
async def test_retry_aliases_preserve_physical_request_origin_and_deduplicate_local_id(tmp_path):
    store, _, run, _ = setup_cycle(tmp_path)
    er = request()
    physical = 'science.review.protocol_retry1'
    engine = RequestEngine(store, {physical: review()}, requests={physical: [er]})
    result = await engine.call(run.run_id, physical, 'scientific_reviewer', payload={})
    engine.checkpoint(run.run_id, **{'science.review': result.model_dump(mode='json'),
        'science.review_evidence_requests': [er]})
    engine.trace_tasks = lambda run_id, key: [run_id + '.' + physical]
    payload = _evidence_handoff(engine, run.run_id, 'science.review', physical)
    assert handed_requests(payload) == [er]
    assert payload['evidence_request_handoff'][0]['source_task_id'] == run.run_id + '.' + physical


@pytest.mark.asyncio
async def test_existing_support_branch_receives_questions_and_returns_its_own_without_extra_stage(tmp_path):
    class RequestSupportEngine(RequestEngine, SupportEngine):
        pass

    store, run, original, proposed, initial = setup_support(tmp_path)
    first, second = request(), request('er2')
    engine = RequestSupportEngine(store, {'science.review': initial, 'science.support_review': review()},
        requests={'science.review': [first], 'science.support_recheck': [second]})
    await review_and_revise(engine, run.run_id, 'science', original=original, proposed=proposed)
    assert handed_requests(engine.payloads['science.support_recheck']) == [first]
    assert handed_requests(engine.payloads['science.support_review']) == [first, second]
    assert engine.invocations == ['science.review', 'science.support_recheck', 'science.support_review']


@pytest.mark.asyncio
async def test_developer_complete_request_reaches_independent_review_through_real_workflow(tmp_path):
    class RequestRuntime(ScientificStageRuntime):
        async def invoke(self, **kwargs):
            role, task_id = kwargs['role'], kwargs['task_id']
            if role != 'developer':
                return await super().invoke(**kwargs)
            self.calls.append({'role': role, 'payload': deepcopy(kwargs['payload'])})
            schema = kwargs['result_schema']
            result = schema.model_validate(self.reply(role, kwargs['task'], kwargs['payload'], task_id))
            envelope = Envelope[schema](schema_version='arc.v1', task_id=task_id,
                subject=kwargs['subject'], result_status='complete', result=result,
                evidence_requests=[EvidenceRequest.model_validate(request())], capability_requests=[], note=None)
            path = self.store.save_artifact(f'tests/{task_id}.json', envelope.model_dump_json())
            prompt = self.store.save_artifact(f'tests/{task_id}.prompt.json', json.dumps({'prompt_id': 'developer.INVOKE'}))
            self.store.put_task(TaskRecord(task_id=task_id, run_id=kwargs['subject'].run_id,
                input_hash='synthetic-input', prompt_hash='synthetic-prompt', model_config_hash='synthetic-model',
                status='ACCEPTED', response_artifact_path=path, rendered_prompt_path=prompt,
                accepted_result=envelope.model_dump(mode='json')))
            return envelope

    store, _, _ = research_store(tmp_path)
    card = store.save_card(research_draft())
    run = store.create_run('develop', card_id=card.card_id, card_version=1)
    runtime = RequestRuntime(store)
    result = await WorkflowEngine(store, runtime, Settings()).execute(run.run_id)
    assert result.status == 'COMPLETED', result.stop_reason
    payload = result.state['task_inputs']['development.science.review']['payload']
    assert handed_requests(payload) == [request()]
    assert payload['evidence_request_handoff'][0]['source_task_id'] == run.run_id + '.development'
    assert [call['role'] for call in runtime.calls] == ['developer', 'scientific_reviewer']
