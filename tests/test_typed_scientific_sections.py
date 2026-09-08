"""Visible nested section contracts and the real runtime's bounded JSON repair."""
from copy import deepcopy
import json
import pytest
from pydantic import ValidationError

from arc.schemas import CardDraft,Envelope,ScientificRevision
from arc.runtime import RuntimePaused
from arc.scientific import apply_scientific_revision
from tests.test_scientific_output_repair import setup_review,encoded_result
from tests.test_scientific_cycle import review,defect,resolution


def revision_payload(target,kind='method'):
    if kind=='method':
        value=deepcopy(target['method'])
        value['necessary_components']=[{'component':'Per-condition response recording',
            'necessity':'The requested contrast needs a separate response for each condition.'}]
    else:
        value=deepcopy(target['contribution'])
        value['knowledge_increment']='Separate the target intervention effects using the supplied comparison.'
    return {'section_updates':[{'field':kind,'value':value}], 'claim_updates':[],
        'remove_claim_ids':[], 'addressed_findings':[resolution()],
        'change_summary':['Represent the necessary comparison explicitly.'], 'abandon':False}


def test_section_schema_exposes_real_card_models_and_discriminator():
    schema=Envelope[ScientificRevision].model_json_schema()
    definitions=schema['$defs']
    items=definitions['ScientificRevision']['properties']['section_updates']['items']
    assert items['discriminator']['propertyName']=='field'
    assert set(items['discriminator']['mapping'])==set(CardDraft.model_fields)-{'claims'}
    assert definitions['MethodSectionUpdate']['properties']['value']=={'$ref':'#/$defs/MethodPlan'}
    assert definitions['MethodPlan']['properties']['necessary_components']['items']=={'$ref':'#/$defs/NecessaryComponent'}
    assert set(definitions['NecessaryComponent']['required'])=={'component','necessity'}
    choices=definitions['Contribution']['properties']['primary_type']['enum']
    assert choices and 'verification' not in choices
    assert definitions['TitleSectionUpdate']['properties']['value']['minLength']==1


@pytest.mark.parametrize('kind',['method','contribution'])
def test_bad_nested_value_fails_revision_parsing_before_application(kind):
    from tests.test_selection import research_draft
    target=research_draft().model_dump(mode='json')
    bad=revision_payload(target,kind)
    if kind=='method':
        bad['section_updates'][0]['value']['necessary_components']=['A component with no object structure']
    else:
        bad['section_updates'][0]['value']['primary_type']='verification'
    with pytest.raises(ValidationError) as caught:
        ScientificRevision.model_validate(bad)
    assert any('value' in err['loc'] and ('necessary_components' in err['loc'] or 'primary_type' in err['loc'])
               for err in caught.value.errors())


@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['method','contribution'])
async def test_nested_revision_error_gets_original_json_correction_before_accepted(tmp_path,kind):
    runtime,store,ledger,requests,responses,payload,subject,_=setup_review(tmp_path)
    runtime.role_models['discovery']='deepseek-v4-pro'
    payload['scientific_review']=review('revise',findings=[defect()]).model_dump(mode='json')
    valid=revision_payload(payload['review_target'],kind)
    bad=deepcopy(valid)
    if kind=='method':
        bad['section_updates'][0]['value']['necessary_components']=['Per-condition response recording']
    else:
        bad['section_updates'][0]['value']['primary_type']='verification'
    responses.extend([encoded_result(bad,subject),encoded_result(valid,subject)])
    try:
        result=await runtime.invoke('discovery','REVISE',payload,ScientificRevision,subject,'task_fixture',tool_profile=[])
        assert result.result.model_dump(mode='json')==valid
        assert len(requests)==2 and len(ledger.list_calls())==2
        assert store.get_task('task_fixture').status=='ACCEPTED'
        state=json.loads(store.read_artifact(store.get_task('task_fixture').response_artifact_path))
        assert state['repair_count']==1
        field='necessary_components' if kind=='method' else 'primary_type'
        assert field in str(state['repair_validation_errors'])
        final=apply_scientific_revision(CardDraft.model_validate(payload['review_target']),result.result)
        assert final.model_dump(mode='json')[kind]==valid['section_updates'][0]['value']
        assert requests[0]['messages'][0]==requests[1]['messages'][0]
    finally:
        await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('defect_kind',['unknown_removal','empty_update','missing_finding','duplicate_finding'])
async def test_revision_addressing_errors_are_repaired_before_acceptance(tmp_path,defect_kind):
    runtime,store,ledger,requests,responses,payload,subject,_=setup_review(tmp_path)
    runtime.role_models['discovery']='deepseek-v4-pro'
    payload['scientific_review']=review('revise',findings=[defect()]).model_dump(mode='json')
    valid=revision_payload(payload['review_target'])
    bad=deepcopy(valid)
    if defect_kind=='unknown_removal':
        bad['remove_claim_ids']=['never_supplied_claim']
    elif defect_kind=='empty_update':
        bad['section_updates']=[]
    elif defect_kind=='missing_finding':
        bad['addressed_findings']=[]
    else:
        bad['addressed_findings']*=2
    responses.extend([encoded_result(bad,subject),encoded_result(valid,subject)])
    try:
        result=await runtime.invoke('discovery','REVISE',payload,ScientificRevision,subject,'task_fixture',tool_profile=[])
        assert result.result.model_dump(mode='json')==valid and len(requests)==2
        assert store.get_task('task_fixture').status=='ACCEPTED'
        assert len(store.list_cards(run_id=subject['run_id']))==1  # The correction only validates output.
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_two_bad_nested_revisions_stop_after_shared_single_allowance(tmp_path):
    runtime,store,ledger,requests,responses,payload,subject,_=setup_review(tmp_path)
    runtime.role_models['discovery']='deepseek-v4-pro'
    payload['scientific_review']=review('revise',findings=[defect()]).model_dump(mode='json')
    bad=revision_payload(payload['review_target'])
    bad['section_updates'][0]['value']['necessary_components']=['Wrong nested shape']
    responses.extend([encoded_result(bad,subject),encoded_result(bad,subject)])
    try:
        with pytest.raises(RuntimePaused,match='INVALID_OUTPUT_AFTER_REPAIR'):
            await runtime.invoke('discovery','REVISE',payload,ScientificRevision,subject,'task_fixture',tool_profile=[])
        assert len(requests)==2 and len(ledger.list_calls())==2
        assert store.get_task('task_fixture').accepted_result is None
    finally:
        await runtime.close()
