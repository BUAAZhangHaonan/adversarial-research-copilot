import json

import pytest
from pydantic import BaseModel

from arc.runtime import RuntimePaused, correction_counts
from arc.schemas import Envelope, SourceRecord, EvidenceRecord
from tests.test_runtime import SUBJECT, answer, setup_runtime, sse


class References(BaseModel):
    source_ids: list[str]
    evidence_ids: list[str]


def reference_answer(sources=(), evidence=()):
    value = answer()
    value['result'] = {'source_ids': list(sources), 'evidence_ids': list(evidence)}
    return value


def source(store):
    return store.register_source(SourceRecord(title='Synthetic original',
        url='https://example.org/fixture', source_type='paper', access_status='retrieved',
        content_origin='original'), content='Original fixture observation.')


async def invoke(runtime, payload):
    return await runtime.invoke('investigator', 'INVOKE', payload, References,
        SUBJECT, 'task_fixture')


@pytest.mark.asyncio
async def test_unknown_source_gets_located_single_correction_before_scientific_contract(tmp_path, monkeypatch):
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses)
    known = source(store)
    responses.extend([sse(json.dumps(reference_answer(['src_typo']))),
                      sse(json.dumps(reference_answer([known.source_id])))])
    seen = []
    def scientific_contract(store, payload, result):
        seen.append(result.source_ids)
        store.validate_references(result)
    monkeypatch.setattr('arc.scientific.validate_scientific_output_contract', scientific_contract)
    result = await invoke(runtime, {'source_ids': [known.source_id]})
    assert result.result.source_ids == [known.source_id]
    assert seen == [[known.source_id]] and len(requests) == 2
    state = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    errors = json.loads(state['repair_validation_errors'][0].split('; ', 1)[1])
    assert errors == [{'loc': ['result', 'source_ids', 0], 'type': 'unknown_source_id',
                      'supplied': 'src_typo', 'visible_candidates': [known.source_id]}]
    assert correction_counts(state) == {'tool_arguments': 0, 'output_json': 1}
    await runtime.close()


@pytest.mark.asyncio
async def test_second_bad_reference_is_rejected_without_extra_correction(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [
        sse(json.dumps(reference_answer(['unknown_a']))),
        sse(json.dumps(reference_answer(['unknown_b'])))])
    with pytest.raises(RuntimePaused, match='INVALID_OUTPUT_AFTER_REPAIR'):
        await invoke(runtime, {})
    assert len(requests) == 2 and store.get_task('task_fixture').accepted_result is None
    state = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    assert 'unknown_b' in state['final_validation_errors'][0]
    assert correction_counts(state) == {'tool_arguments': 0, 'output_json': 1}
    await runtime.close()


@pytest.mark.asyncio
async def test_private_registered_ids_remain_disallowed_and_evidence_diagnostics_are_located(tmp_path):
    runtime, store, ledger, requests = setup_runtime(tmp_path, [])
    known = source(store)
    evidence = store.register_evidence(EvidenceRecord(source_id=known.source_id,
        claim_id='fixture_claim', claim_version=1, claim='Original fixture observation.',
        conditions=['fixture'], locator='L1', excerpt='Original fixture observation.',
        relation='motivates', origin='original', locator_status='verified',
        verification_status='verified', support_explanation='Original observation.'))
    envelope = Envelope[References].model_validate(reference_answer([known.source_id], [evidence.evidence_id]))
    with pytest.raises(ValueError, match='OUTPUT_REFERENCE_INVALID') as error:
        runtime._validate_output_reference_targets(envelope, {}, {'tool_trace': []})
    diagnostics = json.loads(str(error.value).split('; ', 1)[1])
    assert [item['loc'] for item in diagnostics] == [['result', 'source_ids', 0], ['result', 'evidence_ids', 0]]
    assert all(item['type'] == 'reference_not_supplied_to_task' and item['visible_candidates'] == [] for item in diagnostics)
    runtime._validate_output_reference_targets(envelope, {}, {'tool_trace': [
        {'source_ids': [known.source_id], 'evidence_ids': [evidence.evidence_id]}]})
    assert requests == []
    await runtime.close()


@pytest.mark.asyncio
async def test_durable_invalid_response_resume_only_buys_correction_not_original_again(tmp_path):
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses)
    known = source(store)
    responses.extend([sse(json.dumps(reference_answer(['src_typo']))),
                      sse(json.dumps(reference_answer([known.source_id])))])
    validate = runtime._validate_output_reference_targets
    def stop(*args):
        raise SystemExit('Process ended after original response was saved')
    runtime._validate_output_reference_targets = stop
    payload = {'source_ids': [known.source_id]}
    with pytest.raises(SystemExit):
        await invoke(runtime, payload)
    task = store.get_task('task_fixture')
    raw_path = task.response_artifact_path
    raw = store.read_artifact(raw_path)
    assert task.status == 'RESPONSE_SAVED' and len(requests) == 1
    runtime._validate_output_reference_targets = validate
    assert (await invoke(runtime, payload)).result.source_ids == [known.source_id]
    assert len(requests) == 2 and len(ledger.list_calls()) == 2
    assert store.read_artifact(raw_path) == raw
    assert 'src_typo' in requests[1]['messages'][1]['content']
    await runtime.close()
