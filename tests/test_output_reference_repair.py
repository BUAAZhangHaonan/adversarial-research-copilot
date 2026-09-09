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
async def test_unknown_source_gets_located_single_correction_with_independent_scientific_contract(tmp_path, monkeypatch):
    responses = []
    runtime, store, ledger, requests = setup_runtime(tmp_path, responses)
    known = source(store)
    responses.extend([sse(json.dumps(reference_answer(['src_typo']))),
                      sse(json.dumps(reference_answer([known.source_id])))])
    seen = []
    def scientific_contract(store, payload, result, *, check_references=True):
        seen.append(result.source_ids)
        if check_references:
            store.validate_references(result)
    monkeypatch.setattr('arc.scientific.validate_scientific_output_contract', scientific_contract)
    result = await invoke(runtime, {'source_ids': [known.source_id]})
    assert result.result.source_ids == [known.source_id]
    assert seen == [['src_typo'], [known.source_id]] and len(requests) == 2
    state = json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
    errors = json.loads(state['repair_validation_errors'][0].split('; ', 1)[1])
    assert errors['errors'] == [{'loc': ['result', 'source_ids', 0], 'type': 'unknown_source_id',
                      'supplied': 'src_typo', 'reference_kind': 'source'}]
    directory = errors['reference_directory']
    assert directory['sources'][0]['source_id'] == known.source_id
    assert directory['sources'][0]['title'] == known.title
    assert directory['sources'][0]['canonical_url'] == known.url
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
    assert [item['loc'] for item in diagnostics['errors']] == [['result', 'source_ids', 0], ['result', 'evidence_ids', 0]]
    assert all(item['type'] == 'reference_not_supplied_to_task' for item in diagnostics['errors'])
    assert diagnostics['reference_directory']['sources'] == []
    assert diagnostics['reference_directory']['evidence'] == []
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


def test_external_arxiv_candidates_are_exact_visible_and_keep_representation_ambiguity(tmp_path):
    from arc.validation import output_reference_diagnostics
    from arc.store import Store
    store = Store(tmp_path / 'state.sqlite')
    originals = []
    for representation in ['html', 'pdf']:
        originals.append(store.register_source(SourceRecord(title='Same paper',
            url='https://arxiv.org/abs/2107.04034v2', arxiv_id='2107.04034v2',
            source_type='paper', access_status='retrieved', content_origin='original',
            representation_id=representation), content='Original fixture'))
    other_version = store.register_source(SourceRecord(title='Previous version',
        url='https://arxiv.org/abs/2107.04034v1', arxiv_id='2107.04034v1',
        source_type='paper', access_status='metadata_only', content_origin='metadata'))
    private = store.register_source(SourceRecord(title='Invisible paper',
        url='https://arxiv.org/abs/2107.04035', arxiv_id='2107.04035',
        source_type='paper', access_status='metadata_only', content_origin='metadata'))
    visible = {'source': {s.source_id for s in originals + [other_version]}, 'evidence': set()}
    values = ['arxiv:2107.04034', 'https://arxiv.org/pdf/2107.04034v2.pdf',
              'arxiv:2107.04035', 'arxiv:2107.04034v3']
    errors = [{'loc':['result','source_ids',i], 'type':'unknown_source_id',
               'reference_kind':'source', 'supplied':value} for i,value in enumerate(values)]
    result = output_reference_diagnostics(store, errors, visible)
    matches = result['reference_directory']['exact_identity_candidates']
    assert [m['candidate_count'] for m in matches] == [3, 2, 0, 0]
    assert matches[0]['ambiguous'] and matches[1]['ambiguous']
    assert {c['source_id'] for c in matches[1]['candidates']} == {s.source_id for s in originals}
    assert private.source_id not in json.dumps(result)
    assert result['errors'] == errors and not result['reference_directory']['automatic_replacement']


def test_exact_url_preserves_query_identity_and_no_title_guessing(tmp_path):
    from arc.validation import output_reference_diagnostics
    from arc.store import Store
    store = Store(tmp_path / 'state.sqlite')
    known = source(store)
    visible = {'source': {known.source_id}, 'evidence': set()}
    values = [known.url, known.url + '?version=other', known.title]
    errors = [{'loc':['result','source_ids',i], 'type':'unknown_source_id',
               'reference_kind':'source', 'supplied':value} for i,value in enumerate(values)]
    matches = output_reference_diagnostics(store, errors, visible)['reference_directory']['exact_identity_candidates']
    assert [m['candidate_count'] for m in matches] == [1, 0, 0]
    assert matches[0]['candidates'] == [{'source_id': known.source_id, 'match':'exact_url'}]


def test_many_unknown_citations_get_one_bounded_directory_with_exact_matches_first(tmp_path):
    from arc.validation import output_reference_diagnostics
    from arc.store import Store
    store = Store(tmp_path / 'state.sqlite')
    sources = [store.register_source(SourceRecord(title=f'Paper {i}',
        url=f'https://arxiv.org/abs/2107.{i:05}', arxiv_id=f'2107.{i:05}',
        source_type='paper', access_status='metadata_only', content_origin='metadata'))
        for i in range(250)]
    errors = [{'loc':['result','source_ids',i], 'type':'unknown_source_id',
               'reference_kind':'source', 'supplied':'arxiv:2107.00249'} for i in range(22)]
    visible = {'source': {s.source_id for s in sources}, 'evidence': set()}
    result = output_reference_diagnostics(store, errors, visible)
    directory = result['reference_directory']
    assert len(directory['sources']) == 40 and directory['omitted_source_count'] == 210
    assert directory['sources'][0]['source_id'] == sources[-1].source_id
    assert len(directory['exact_identity_candidates']) == 1
    assert all('visible_candidates' not in error for error in result['errors'])
    assert len(json.dumps(result)) < 25000


def test_malformed_url_and_oversized_error_values_cannot_break_or_expand_diagnostics(tmp_path):
    from arc.validation import output_reference_diagnostics
    from arc.store import Store
    store = Store(tmp_path / 'state.sqlite')
    known = source(store)
    values = ['http://[bad', 'x' * 100000, {'wrong': 'y' * 100000}]
    errors = [{'loc':['result','source_ids',i], 'type':'unknown_source_id',
               'reference_kind':'source', 'supplied':value} for i,value in enumerate(values)]
    result = output_reference_diagnostics(store, errors,
        {'source': {known.source_id}, 'evidence': set()})
    assert result['errors'][0]['supplied'] == 'http://[bad'
    assert result['errors'][1]['supplied_truncated']
    assert result['errors'][1]['supplied_original_chars'] == 100000
    assert result['errors'][2]['supplied_representation'] == 'json'
    assert result['errors'][2]['supplied_truncated']
    assert all(m['candidate_count'] == 0 for m in result['reference_directory']['exact_identity_candidates'])
    assert len(json.dumps(result)) < 6000
    assert errors[1]['supplied'] == 'x' * 100000  # Diagnostic rendering never rewrites the output.
