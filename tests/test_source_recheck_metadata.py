"""An unavailable original can be diagnosed, never promoted to verified evidence."""
from __future__ import annotations

import copy
import json

import pytest

from arc.config import Settings
from arc.runtime import RuntimePaused
from arc.schemas import SourceRecord, TaskRecord
from arc.workflows import WorkflowEngine, WorkflowPause
from tests.test_selection import research_store
from tests.test_workflows import ScriptedRuntime, campaign_run


def metadata_case(tmp_path, case='withdrawn'):
    store, _, _ = research_store(tmp_path)
    source = store.register_source(SourceRecord(source_id='src_metadata',
        title='Metadata without returned paper text', url='https://example.org/metadata',
        source_type='paper', access_status='metadata_only', content_origin='metadata'))
    _, run = campaign_run(store, max_draws=1)
    withdrawn = {'claim': 'The original claim cannot be checked from available metadata.',
        'conditions': ['No original text was returned.'], 'source_id': source.source_id,
        'locator': None, 'locator_status': 'source_unavailable', 'relation': 'unresolved',
        'origin': 'inference', 'excerpt': None,
        'support_explanation': 'The empty cached record does not support the earlier quotation.'}
    bad_quote = {**withdrawn, 'locator_status': 'verified', 'locator': 'chars:0:29',
        'relation': 'supports', 'origin': 'original', 'excerpt': 'The authors prove the claim.'}

    class MetadataRuntime(ScriptedRuntime):
        async def invoke(self, **kw):
            if kw['task_id'].endswith('.shared'):
                if self.store.get_task(kw['task_id']) is None:
                    result = super().reply('investigator', 'INVOKE', kw['payload'], kw['task_id'])
                    result['findings'] = [bad_quote]
                    path = self.store.save_artifact('tests/rejected_metadata.json', json.dumps({
                        'response': {'message': {'content': json.dumps({'result': result})}}}))
                    self.store.put_task(TaskRecord(task_id=kw['task_id'], run_id=run.run_id,
                        input_hash='frozen', prompt_hash='frozen', model_config_hash='frozen',
                        status='PAUSED_PROTOCOL', error='excerpt_not_in_returned_source',
                        response_artifact_path=path))
                raise RuntimePaused('PAUSED_PROTOCOL', 'excerpt_not_in_returned_source')
            assert kw['task_id'].endswith('.source_recheck')
            assert kw['tool_profile'] == ['read_record', 'request_capability']
            assert kw['payload']['target_source_ids'] == [source.source_id]
            return await super().invoke(**kw)

        def reply(self, role, task, payload, task_id):
            result = super().reply(role, task, payload, task_id)
            if task_id.endswith('.source_recheck'):
                result['findings'] = [copy.deepcopy(withdrawn)]
                result['source_access_limits'] = ['The requested source has metadata but no cached body.']
                if case == 'verified_quote':
                    result['findings'] = [bad_quote]
                elif case == 'mixed_findings':
                    result['findings'].append(bad_quote)
                elif case == 'mixed_contrary':
                    result['contrary_findings'] = [bad_quote]
                elif case == 'no_limit':
                    result['source_access_limits'] = []
                elif case == 'no_matching_finding':
                    result['findings'] = []
                elif case == 'still_supports':
                    result['findings'][0]['relation'] = 'supports'
                elif case == 'still_original':
                    result['findings'][0]['origin'] = 'original'
            return result

        def tool_trace(self, task_id):
            if task_id.endswith('.shared'):
                return [{'name': 'search_literature', 'status': 'completed',
                    'source_ids': [source.source_id], 'result': {'is_error': False,
                    'source_ids': [source.source_id], 'sources': []}}]
            trace = {'name': 'read_record', 'status': 'completed', 'source_ids': [source.source_id],
                'arguments': {'record_id': source.source_id}, 'result': {'source_id': source.source_id,
                    'content': '', 'requires_source_fetch': True, 'cached_content_chars': 0}}
            if case == 'no_read':
                return []
            if case == 'wrong_source':
                trace['arguments']['record_id'] = 'src_synthetic'
            elif case == 'failed_read':
                trace['status'] = 'failed'
            elif case == 'fetch_not_required':
                trace['result']['requires_source_fetch'] = False
            elif case == 'nonempty_cache':
                trace['result']['cached_content_chars'] = 500
            return [trace]

    runtime = MetadataRuntime(store)
    return store, run, runtime, WorkflowEngine(store, runtime, Settings())


@pytest.mark.asyncio
async def test_metadata_only_recheck_withdraws_quote_and_resumes_without_paid_replay(tmp_path):
    store, run, runtime, engine = metadata_case(tmp_path)
    result = await engine.investigate(run.run_id, 'shared', ['Check the original claim.'], fresh=True)
    assert result.findings[0].locator_status == 'source_unavailable'
    assert result.findings[0].excerpt is None
    assert result.findings[0].relation == 'unresolved'
    assert result.source_access_limits
    assert len(runtime.calls) == 1
    evidence = store.list_evidence(run_id=run.run_id)
    assert len(evidence) == 1
    assert evidence[0].verification_status == 'unverified'
    assert evidence[0].locator_status != 'verified'
    assert evidence[0].origin == 'inference' and evidence[0].relation == 'unresolved'
    assert evidence[0].excerpt is None
    rejected = store.get_task(run.run_id + '.shared')
    raw = store.read_artifact(rejected.response_artifact_path)
    assert rejected.status == 'PAUSED_PROTOCOL' and rejected.accepted_result is None
    assert store.get_task(run.run_id + '.shared.source_recheck').status == 'ACCEPTED'
    assert store.get_run(run.run_id).state['shared_trace_tasks'] == [
        run.run_id + '.shared', run.run_id + '.shared.source_recheck']
    resumed = await engine.investigate(run.run_id, 'shared', ['Check the original claim.'], fresh=True)
    assert resumed == result and len(runtime.calls) == 1
    assert store.list_evidence(run_id=run.run_id) == evidence
    assert store.get_task(run.run_id + '.shared') == rejected
    assert store.read_artifact(rejected.response_artifact_path) == raw


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['no_read', 'wrong_source', 'failed_read', 'verified_quote',
    'mixed_findings', 'mixed_contrary', 'no_limit', 'no_matching_finding', 'still_supports',
    'still_original', 'fetch_not_required', 'nonempty_cache'])
async def test_metadata_only_recheck_rejects_missing_read_or_incomplete_withdrawal(tmp_path, case):
    store, run, runtime, engine = metadata_case(tmp_path, case)
    for attempt in range(2):
        with pytest.raises(WorkflowPause, match='source_recheck_original_not_read'):
            await engine.investigate(run.run_id, 'shared', ['Check the original claim.'], fresh=True)
        assert len(runtime.calls) == 1
        assert 'shared' not in store.get_run(run.run_id).state
        assert 'shared_trace_tasks' not in store.get_run(run.run_id).state
        assert store.list_evidence(run_id=run.run_id) == []
        rejected = store.get_task(run.run_id + '.shared')
        assert rejected.status == 'PAUSED_PROTOCOL' and rejected.accepted_result is None
