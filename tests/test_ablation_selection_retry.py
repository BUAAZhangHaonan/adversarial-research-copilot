from copy import deepcopy
import json
import pytest
from arc.budget import BudgetLedger
from arc.comparison_retry import prepare_ablation_selection_retry
from arc.evaluation import _frozen_call
from arc.schemas import Envelope, SelectorResult, Subject, TaskRecord
from arc.store import StateError
from tests.test_selection import research_store, research_draft, novelty_result, selection_result


def environment(tmp_path, *, valid=False):
    store, source, evidence = research_store(tmp_path)
    ledger = BudgetLedger(store.db_path)
    ledger.create_account('parent', '100')
    experiment = 'ablation_fixture'; rid = experiment + '.B'
    ledger.create_account(rid, '20', parent_id='parent')
    run = store.create_run('evaluation', run_id=rid, budget_account_id=rid)
    card = store.save_card(research_draft(), run_id=rid)
    subject = {'campaign_id': None, 'run_id': rid, 'card_id': card.card_id, 'card_version': card.version}
    judgment = selection_result(); judgment.selection_checks.resource_path.status = 'supported' if valid else 'unknown'
    payload = {'card': card.model_dump(mode='json'), 'novelty': novelty_result().model_dump(mode='json')}
    envelope = {'schema_version': 'arc.v1', 'task_id': rid+'.selection', 'subject': subject,
        'result_status': 'complete', 'result': judgment.model_dump(mode='json'),
        'evidence_requests': [], 'capability_requests': [], 'note': None}
    prompt = store.save_artifact('fixture/prompt.json', json.dumps({'prompt_id':'selector.INVOKE'}))
    raw = store.save_artifact('fixture/response.json', json.dumps({'subject':subject,
        'response':{'message':{'content':json.dumps(envelope)}}, 'original_tools':[], 'tool_trace':[]}))
    task = TaskRecord(task_id=envelope['task_id'], run_id=rid, input_hash='fixture',
        prompt_hash='fixture', model_config_hash='fixture', status='ACCEPTED',
        rendered_prompt_path=prompt, response_artifact_path=raw, accepted_result=envelope)
    store.put_task(task)
    material_path = f'functional-evaluations/{experiment}/manifest.json'
    store.save_artifact(material_path, json.dumps({'experiment_id':experiment,'parent_id':'parent',
        'material':{'sources':[source.model_dump(mode='json')],'evidence':[evidence.model_dump(mode='json')]}}))
    store.update_run(rid, card_id=card.card_id, card_version=card.version,
        status='PAUSED_PROTOCOL', stop_reason='MAIN_REPORT_PREREQUISITE_UNESTABLISHED',
        state={'functional_experiment':experiment,'condition':'B','material_path':material_path,
            'task_inputs':{'selection':{'subject':subject,'payload':payload}},
            'comparison_envelopes':{'selection':envelope,'novelty':{'result':payload['novelty']},
                                    'compose':{'preserved_fixture':'original candidate'}}})
    return store, ledger, experiment, rid, card, task, payload


@pytest.mark.asyncio
async def test_explicit_retry_preserves_accepted_failure_card_material_cost_and_executes_new_task(tmp_path):
    store, ledger, experiment, rid, card, old, payload = environment(tmp_path)
    before = old.model_dump(mode='json'); raw = store.read_artifact(old.response_artifact_path)
    prior = deepcopy(store.get_run(rid).state); budget = ledger.summary('parent')
    entry = prepare_ablation_selection_retry(store, ledger, experiment, 'B', 'Correct the inconsistent selection independently.')
    assert entry['replacement_key'] == 'selection.protocol_retry1'
    assert store.get_task(old.task_id).model_dump(mode='json') == before
    assert store.read_artifact(old.response_artifact_path) == raw
    assert ledger.summary('parent') == budget
    assert store.get_card(card.card_id, card.version) == card
    assert store.get_run(rid).state['comparison_envelopes'] == {k:v for k,v in prior['comparison_envelopes'].items() if k!='selection'}
    audit=json.loads(store.read_artifact(entry['audit_path']))
    assert audit['superseded_cached_envelope'] == old.accepted_result
    assert audit['protocol_retry']['previous_response_was_accepted'] is True
    assert audit['protocol_retry']['validation_errors'][0]['loc'] == ['result','selection_checks','resource_path','status']
    calls=[]
    class Runtime:
        async def invoke(self, **kwargs):
            calls.append(kwargs)
            return Envelope[SelectorResult](schema_version='arc.v1', task_id=kwargs['task_id'],
                subject=kwargs['subject'], result_status='complete', result=selection_result('LEAD_ONLY'),
                evidence_requests=[], capability_requests=[], note=None)
    result=await _frozen_call(store, Runtime(), rid, 'selection', 'selector', payload=payload)
    assert result.selection=='LEAD_ONLY' and len(calls)==1
    assert calls[0]['task_id']==rid+'.selection.protocol_retry1'
    assert calls[0]['payload']['protocol_retry']['request_reason']=='Correct the inconsistent selection independently.'
    await _frozen_call(store, Runtime(), rid, 'selection', 'selector', payload=payload)
    assert len(calls)==1


@pytest.mark.parametrize('change', ['stop_reason','cached_response','input_card','valid_judgment','wrong_condition'])
def test_application_retry_rejects_unrelated_or_changed_results(tmp_path, change):
    store, ledger, experiment, rid, card, task, payload=environment(tmp_path, valid=change=='valid_judgment')
    run=store.get_run(rid); state=deepcopy(run.state)
    if change=='stop_reason':store.update_run(rid,stop_reason='unrelated_failure')
    elif change=='cached_response':
        state['comparison_envelopes']['selection']['result']['next_action']='Changed'
        store.update_run(rid,state=state)
    elif change=='input_card':
        state['task_inputs']['selection']['payload']['card']['draft']['title']='Changed'
        store.update_run(rid,state=state)
    elif change=='valid_judgment':
        pass
    else:
        state['condition']='A';store.update_run(rid,state=state)
    with pytest.raises(StateError):prepare_ablation_selection_retry(store,ledger,experiment,'B','Explicit correction')
    assert 'comparison_task_retries' not in store.get_run(rid).state


@pytest.mark.parametrize('accepted_again', [False, True])
def test_explicit_second_retry_can_correct_json_failure_or_repeated_application_failure(tmp_path, accepted_again):
    store, ledger, experiment, rid, card, old, payload=environment(tmp_path)
    first=prepare_ablation_selection_retry(store,ledger,experiment,'B','First explicit correction')
    key=first['replacement_key']; tid=rid+'.'+key
    envelope=deepcopy(old.accepted_result);envelope['task_id']=tid
    response=store.save_artifact('fixture/retry1.json',json.dumps({'subject':envelope['subject'],
        'original_tools':[], 'tool_trace':[],
        'response':{'message':{'content':json.dumps(envelope) if accepted_again else '{bad'}},
        'final_validation_errors':[] if accepted_again else [{'type':'json_invalid'}]}))
    task=old.model_copy(update={'task_id':tid,'status':'ACCEPTED' if accepted_again else 'PAUSED_PROTOCOL',
        'accepted_result':envelope if accepted_again else None,'response_artifact_path':response,
        'error':None if accepted_again else 'INVALID_OUTPUT_AFTER_REPAIR'})
    store.put_task(task)
    state=deepcopy(store.get_run(rid).state)
    if accepted_again:state['comparison_envelopes']['selection']=envelope
    store.update_run(rid,state=state,status='PAUSED_PROTOCOL',
        stop_reason='MAIN_REPORT_PREREQUISITE_UNESTABLISHED' if accepted_again else 'INVALID_OUTPUT_AFTER_REPAIR')
    second=prepare_ablation_selection_retry(store,ledger,experiment,'B','Second explicit correction')
    assert second['replacement_key']=='selection.protocol_retry2'
    assert second['source_task_id']==tid
    assert store.get_task(old.task_id)==old
    assert store.get_task(tid).accepted_result==(envelope if accepted_again else None)
