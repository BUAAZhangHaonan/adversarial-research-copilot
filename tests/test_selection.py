"""Independent synthetic research cases, not expert quality labels."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from arc.schemas import CardDraft, SourceRecord, EvidenceRecord, SelectorResult, NoveltyResult
from arc.store import Store, StateError
from arc.validation import validate_selection


def research_store(tmp_path: Path):
    store=Store(tmp_path/'state.sqlite')
    text='SYNTHETIC TEST SOURCE. Section 1: Moving relevant facts farther away lowered recall. Distractor count also changed. Section 2: The authors ask whether distance or interference caused the result; they do not isolate the variables. Section 3: A controlled factorial intervention can independently change distance and distractor count.'
    source=store.register_source(SourceRecord(source_id='src_synthetic',title='Synthetic distance and distractor study',url=None,source_type='user_material',access_status='retrieved',content_origin='original'),content=text)
    excerpt='Moving relevant facts farther away lowered recall. Distractor count also changed.'
    start=text.index(excerpt)
    evidence=store.register_evidence(EvidenceRecord(evidence_id='ev_synthetic',source_id=source.source_id,claim_id='claim_observation',claim_version=1,claim='Distance and distractor count covary in an observed recall decrease.',conditions=['synthetic controlled recall task'],locator=f'chars:{start}:{start+len(excerpt)}',excerpt=excerpt,relation='motivates',origin='original',locator_status='verified',verification_status='verified',support_explanation='The quoted two sentences support the motivation; they do not establish which factor is causal.'))
    return store,source,evidence


def research_draft(evidence_id='ev_synthetic',source_id='src_synthetic'):
    return CardDraft.model_validate({
        'title':'Separating distance from distractor interference',
        'problem_anchor':{'question':'Does distance or distractor interference cause the recall decrease?','research_object':'retrieval in controlled sequence tasks','conditions':['same model and inference budget'],'anti_scope':['no model pretraining','no claim that the proposed experiment has run']},
        'contribution':{'primary_type':'new_mechanism','secondary_types':[],'knowledge_increment':'Identify which intervention changes recall under equal budget.','decision_changed':'Choose context placement or interference reduction as the next intervention.'},
        'motivation':{'observation_or_deficit':'Prior observation confounds distance with distractor count.','evidence_ids':[evidence_id],'unresolved_assumptions':['Controlled task effects may not generalize.']},
        'closest_work_delta':{'source_ids':[source_id],'established_claim':'Covariation, not causal separation.','remaining_claim':'The independently controlled response.','search_limits':['Synthetic local fixture only.']},
        'hypotheses':{'main_or_competing_explanations':['Distance causes degradation.','Distractor interference causes degradation.'],'distinct_predictions':['Varying distance alone changes recall.','Varying distractors alone changes recall.'],'favored_only_if_justified':None},
        'method':{'simplest_path':'A two-factor controlled recall task.','necessary_components':[],'stitching_assessment':'Routine evaluation only; no contribution from combining modules.'},
        'minimal_test':{'intervention':'Factorially vary fact distance and distractor count.','controls':['same weights','same tokens','same answerable facts'],'measurements':['fact recall accuracy'],'positive_controls':['nearby fact with no distractors remains answerable'],'outcome_interpretations':[{'outcome':'Only distance intervention changes recall','interpretation':'Supports a distance-specific explanation','validity_limit':'Requires the positive control and unchanged token budget'}],'confounds_not_yet_ruled_out':['synthetic data validity']},
        'resources':{'gpu_type':'RTX 3090','gpu_memory_gb_assumption':24,'gpu_count':1,'training_gpu_hours_range':None,'inference_gpu_hours_range':{'lower':1,'upper':4,'unit':'GPU-hours'},'wall_hours_range':{'lower':2,'upper':8,'unit':'hours'},'workload_assumptions':{'model_size':'7B','precision':'4-bit','sequence_length':2048,'data_amount':'100 synthetic tasks','steps':None,'parallelism':'single GPU','non_gpu_steps':'task construction'},'estimate_basis':'Synthetic fixture estimate for test only, not a measured public throughput.','uncertainty':'Broad estimate; no research experiment executed.'},
        'risks':{'decisive_risks':['The manipulation may change difficulty beyond the named factors.'],'missing_prerequisites':[],'reopen_conditions':['New evidence of an uncontrolled factor requires redesign.']},
        'claims':[]})


def novelty_result(coverage='not_covered'):
    return NoveltyResult.model_validate({'closest_works':[{'source_id':'src_synthetic','evidence_ids':['ev_synthetic'],'established_claim':'The source observes covariation and asks the question.','conditions':['synthetic controlled recall task'],'card_claim':'The proposed controlled causal separation.','coverage':coverage,'rationale':'Section 2 explicitly leaves the causal distinction unanswered.'}],
        'contribution_coverage':coverage,'defensible_delta':'A question was asked but not answered.','search_scope':'Synthetic local test source only.','unchecked_items':['External literature is not tested by this fixture.'],'recommended_selection_effect':'Assess the new intervention rather than question-word overlap.'})


def selection_result(selection='MAIN_REPORT',**overrides):
    payload={'selection':selection,'assessment':{'MAIN_REPORT':'PROMISING','LEAD_ONLY':'NEEDS_EVIDENCE','NOT_RETAINED':'REJECTED'}[selection],
        'contribution_summary':'Separate distance and distractor effects.','why_worth_investigating':'Either causal answer changes the next intervention.','closest_work_delta':'The source asks but does not isolate the factors.','hypothesis_plausibility':'Both explanations fit the observed covariation; neither is yet confirmed.','test_identifiability':'Two independent interventions and a positive control.','stitching_check':'No gratuitous components.','resource_assessment':'One 24GB GPU under stated assumptions.','unverified_assumptions':['Outcome of the proposed experiment.'],'decisive_risks':['Manipulation validity.'],'evidence_ids':['ev_synthetic'],'next_action':'HANDOFF_EXPERIMENT','reopening_condition':'Restore a valid manipulation when the control fails.',
        'selection_checks':{key:{'status':'supported','evidence_ids':['ev_synthetic'] if key=='motivation' else [],'rationale':reason} for key,reason in {'motivation':'Source Section 1 records the covariation.','knowledge_delta':'The causal distinction is not in Section 2.','test_identifiability':'Interventions separate the factors.','resource_path':'Small inference workload.','stitching':'Routine measurement requires no added architecture.'}.items()},
        'stitching_type':'routine_components','meaningful_gain_basis':None,'interaction_prediction':None,'matched_budget_test':None}
    payload.update(overrides)
    return SelectorResult.model_validate(payload)


def test_untested_but_identifiable_hypothesis_can_be_main_report(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    judgment=selection_result()
    validate_selection(store,card,judgment,novelty_result())
    assert judgment.selection=='MAIN_REPORT'
    assert 'Outcome' in judgment.unverified_assumptions[0]


def test_two_informative_mechanisms_do_not_require_a_favored_winner(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    assert card.draft.hypotheses.favored_only_if_justified is None
    validate_selection(store,card,selection_result(),novelty_result())


def test_unidentifiable_test_is_a_lead_not_a_main_card(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    judgment=selection_result('LEAD_ONLY',test_identifiability='Only final accuracy; intervention changes both factors.')
    judgment.selection_checks.test_identifiability.status='unknown'
    validate_selection(store,card,judgment,novelty_result())
    with pytest.raises(ValueError,match='PREREQUISITE'):
        validate_selection(store,card,selection_result(selection_checks=judgment.selection_checks.model_dump()),novelty_result())


def test_ordinary_stitching_cannot_enter_main_report(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    rejected=selection_result('NOT_RETAINED',stitching_type='unsupported_stitching',stitching_check='Retrieval plus graph plus critic has no necessary interaction claim.')
    validate_selection(store,card,rejected,novelty_result())
    with pytest.raises(ValueError,match='UNSUPPORTED_STITCHING'):
        validate_selection(store,card,selection_result(stitching_type='unsupported_stitching'),novelty_result())


def test_combination_exception_needs_both_gain_and_interaction(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    for missing in ('meaningful_gain_basis','interaction_prediction','matched_budget_test'):
        kwargs={'stitching_type':'combination_exception','meaningful_gain_basis':'The two observed bottlenecks prevent success unless both are removed.','interaction_prediction':'Joint intervention changes the interaction contrast rather than either main effect.','matched_budget_test':'Four arms use the same information and tokens.'}
        kwargs[missing]=None
        with pytest.raises(ValueError,match='COMBINATION_EXCEPTION'):
            validate_selection(store,card,selection_result(**kwargs),novelty_result())


def test_previously_asked_question_is_not_covered_contribution(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    closest=novelty_result('not_covered')
    assert closest.closest_works[0].source_id==card.draft.closest_work_delta.source_ids[0]
    validate_selection(store,card,selection_result(),closest)
    with pytest.raises(ValueError,match='COVERAGE_UNESTABLISHED'):
        validate_selection(store,card,selection_result(),novelty_result('covered'))


def test_unknown_original_or_invented_evidence_cannot_be_main_report(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    with pytest.raises(StateError,match='unknown_evidence_id'):
        validate_selection(store,card,selection_result(evidence_ids=['ev_invented']),novelty_result())
    with pytest.raises(ValueError,match='COVERAGE_UNESTABLISHED'):
        validate_selection(store,card,selection_result(),novelty_result('unknown'))


def test_covered_work_cannot_borrow_verified_evidence_from_another_source(tmp_path):
    store,_,_=research_store(tmp_path)
    other=store.register_source(SourceRecord(source_id='src_other',title='Synthetic unrelated image study',url=None,source_type='user_material',access_status='retrieved',content_origin='original'),content='SYNTHETIC OTHER SOURCE: This record studies image corruption, not controlled recall.')
    card=store.save_card(research_draft())
    novelty=novelty_result('covered')
    novelty.closest_works[0].source_id=other.source_id
    assert store.get_record('ev_synthetic')['verification_status']=='verified'
    with pytest.raises(ValueError,match='COVERAGE_EVIDENCE_SOURCE_MISMATCH'):
        validate_selection(store,card,selection_result('NOT_RETAINED'),novelty)


@pytest.mark.parametrize('gate',['motivation','knowledge_delta','test_identifiability','resource_path'])
def test_required_knowledge_gates_cannot_be_marked_not_applicable(tmp_path,gate):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    judgment=selection_result()
    getattr(judgment.selection_checks,gate).status='not_applicable'
    with pytest.raises(ValueError,match='MAIN_REPORT_PREREQUISITE_UNESTABLISHED'):
        validate_selection(store,card,judgment,novelty_result())


def test_not_applicable_is_allowed_only_for_stitching_check(tmp_path):
    store,_,_=research_store(tmp_path)
    card=store.save_card(research_draft())
    judgment=selection_result(stitching_type='not_applicable')
    judgment.selection_checks.stitching.status='not_applicable'
    validate_selection(store,card,judgment,novelty_result())
