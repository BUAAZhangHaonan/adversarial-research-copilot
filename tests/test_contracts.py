"""Independent adversarial examples for the public scientific protocol."""
import pytest
from pydantic import ValidationError
from arc.schemas import (Envelope, Subject, FrameResult, CardDraft, NumericRange,
    ResourceEstimate, NextDrawResult, ModeratorResult, RESULT_SCHEMAS, SelectorResult)

def card_payload():
    # Synthetic data, deliberately no purported papers or fabricated source IDs.
    return {
        "title":"合成：测量误差的作用", "problem_anchor":{"question":"测量误差是否改变结论？","research_object":"合成测量系统","conditions":["同预算"],"anti_scope":["不训练大模型"]},
        "contribution":{"primary_type":"new_boundary","secondary_types":[],"knowledge_increment":"确定结论的适用边界","decision_changed":"选择测量方式"},
        "motivation":{"observation_or_deficit":"已记录的测量差异","evidence_ids":[],"unresolved_assumptions":[]},
        "closest_work_delta":{"source_ids":[],"established_claim":"已有条件下成立","remaining_claim":"噪声条件待查","search_limits":["合成测试"]},
        "hypotheses":{"main_or_competing_explanations":["测量误差","实际效应"],"distinct_predictions":["改变测量时仅一种预测改变"],"favored_only_if_justified":None},
        "method":{"simplest_path":"改变测量噪声","necessary_components":[],"stitching_assessment":"常规测量部件"},
        "minimal_test":{"intervention":"改变噪声","controls":["固定数据"],"measurements":["误差"],"positive_controls":["已知信号"],"outcome_interpretations":[{"outcome":"误差改变","interpretation":"支持测量解释","validity_limit":"阳性对照正常"}],"confounds_not_yet_ruled_out":[]},
        "resources":{"gpu_type":"RTX 3090","gpu_memory_gb_assumption":24,"gpu_count":1,"training_gpu_hours_range":None,"inference_gpu_hours_range":{"lower":1,"upper":2,"unit":"GPU-hours"},"wall_hours_range":{"lower":1,"upper":3,"unit":"hours"},"workload_assumptions":{"model_size":"1B","precision":"fp16","sequence_length":1024,"data_amount":"1000 cases","steps":None,"parallelism":"one GPU","non_gpu_steps":"data reading"},"estimate_basis":"synthetic estimate","uncertainty":"range only"},
        "risks":{"decisive_risks":[],"missing_prerequisites":[],"reopen_conditions":[]},
    }

def selection_payload():
    check={"status":"supported","evidence_ids":[],"rationale":"synthetic check"}
    return {"selection":"MAIN_REPORT","assessment":"PROMISING","contribution_summary":"新边界",
        "why_worth_investigating":"两种结果都有价值","closest_work_delta":"此前未回答", "hypothesis_plausibility":"动机成立但尚未实验", "test_identifiability":"对照可区分",
        "stitching_check":"常规部件","resource_assessment":"可行","unverified_assumptions":["实验尚未执行"],"decisive_risks":[],"evidence_ids":[],"next_action":"HANDOFF_EXPERIMENT","reopening_condition":None,
        "selection_checks":{k:dict(check) for k in ["motivation","knowledge_delta","test_identifiability","resource_path","stitching"]},"stitching_type":"routine_components","meaningful_gain_basis":None,"interaction_prediction":None,"matched_budget_test":None}

def test_all_thirteen_registered_semantic_contracts_are_closed():
    assert set(RESULT_SCHEMAS)=={"investigator","librarian","discovery.FRAME","discovery.NEXT_DRAW","discovery.COMPOSE","novelty_examiner","selector","developer","proposer","skeptic","moderator","reporter","evaluator"}
    for schema in RESULT_SCHEMAS.values():
        assert schema.model_json_schema()["additionalProperties"] is False
        with pytest.raises(ValidationError): schema.model_validate({})

def test_complete_envelope_cannot_omit_payload_or_invent_execution_control():
    common=dict(schema_version="arc.v1",task_id="t1",subject=Subject(campaign_id=None,run_id=None,card_id=None,card_version=None),result_status="complete",result=None,evidence_requests=[],capability_requests=[],note=None)
    with pytest.raises(ValidationError): Envelope[FrameResult](**common)
    common.update(result_status="blocked",note="source unavailable")
    assert Envelope[FrameResult](**common).result is None
    with pytest.raises(ValidationError): Envelope[FrameResult](**common,run_status="COMPLETED")

def test_needs_evidence_must_be_actionable():
    with pytest.raises(ValidationError):
        Envelope[FrameResult](schema_version="arc.v1",task_id="t",subject=Subject(campaign_id=None,run_id=None,card_id=None,card_version=None),result_status="needs_evidence",result=None,evidence_requests=[],capability_requests=[],note="search")

def prerequisite_request():
    return {"request_local_id":"request1","claim_id":None,"issue_id":None,"draw_id":None,
        "question":"Does the original describe this comparison?","target_source_ids":["registered_source"],
        "queries":[],"purpose":"Check the proposed investigation boundary.",
        "decision_if_supported":"Include the comparison in the evidence map.",
        "decision_if_contradicted":"Record the missing comparison as unresolved."}

def prerequisite_envelope(request=None,**subject_updates):
    subject={"campaign_id":"campaign1","run_id":"run1","card_id":None,"card_version":None}
    subject.update(subject_updates)
    return {"schema_version":"arc.v1","task_id":"run1.shared_investigation","subject":subject,
        "result_status":"needs_evidence","result":None,"evidence_requests":[request or prerequisite_request()],
        "capability_requests":[],"note":"A specific source question remains open."}

@pytest.mark.parametrize("status",["complete","needs_evidence","blocked"])
def test_pre_card_evidence_request_is_bound_to_enclosing_task_and_run(status):
    from arc.schemas import EvidenceRequest
    payload=prerequisite_envelope()
    payload["result_status"]=status
    if status=="complete":
        payload["result"]={"mandate":{"topic":"research question","research_object":"fixed domain","scope_in":[],"scope_out":[],"known_constraints":[],"unknown_constraints":[]},"initial_search_questions":[]}
    envelope=Envelope[FrameResult].model_validate(payload)
    assert envelope.task_id=="run1.shared_investigation"
    assert envelope.subject.campaign_id=="campaign1" and envelope.subject.run_id=="run1"
    assert envelope.evidence_requests[0].model_dump()==payload["evidence_requests"][0]
    assert set(EvidenceRequest.model_fields)==set(prerequisite_request())
    assert envelope.model_dump()==payload

@pytest.mark.parametrize("subject",[
    {"card_id":"card1","card_version":1},
    {"campaign_id":None},{"run_id":None},{"campaign_id":""},{"run_id":""},
])
def test_unbound_evidence_request_requires_pre_card_campaign_and_run(subject):
    with pytest.raises(ValidationError,match="evidence_request_requires_subject"):
        Envelope[FrameResult].model_validate(prerequisite_envelope(**subject))

@pytest.mark.parametrize("target",["claim_id","issue_id","draw_id"])
def test_existing_entity_evidence_requests_keep_explicit_subject(target):
    request=prerequisite_request(); request[target]="existing_id"
    envelope=Envelope[FrameResult].model_validate(prerequisite_envelope(request,card_id="card1",card_version=1))
    assert getattr(envelope.evidence_requests[0],target)=="existing_id"

@pytest.mark.parametrize("field",["question","purpose","decision_if_supported","decision_if_contradicted"])
def test_pre_card_request_still_requires_concrete_question_and_decisions(field):
    request=prerequisite_request(); request[field]=""
    with pytest.raises(ValidationError): Envelope[FrameResult].model_validate(prerequisite_envelope(request))
    del request[field]
    with pytest.raises(ValidationError): Envelope[FrameResult].model_validate(prerequisite_envelope(request))

def test_pre_card_request_still_requires_search_target_and_actual_task():
    request=prerequisite_request(); request["target_source_ids"]=[]
    with pytest.raises(ValidationError,match="evidence_request_requires_target"):
        Envelope[FrameResult].model_validate(prerequisite_envelope(request))
    request["queries"]=["specific original source question"]
    assert Envelope[FrameResult].model_validate(prerequisite_envelope(request)).evidence_requests[0].queries
    payload=prerequisite_envelope(); payload["task_id"]=""
    with pytest.raises(ValidationError): Envelope[FrameResult].model_validate(payload)

def test_card_complete_without_fabricated_probability_or_experimental_success():
    payload=card_payload()
    assert CardDraft.model_validate(payload).hypotheses.favored_only_if_justified is None
    payload["success_probability"]=0.9
    with pytest.raises(ValidationError): CardDraft.model_validate(payload)

@pytest.mark.parametrize("missing",["motivation","hypotheses","minimal_test","resources","closest_work_delta"])
def test_card_cannot_silently_drop_required_research_material(missing):
    payload=card_payload(); payload.pop(missing)
    with pytest.raises(ValidationError): CardDraft.model_validate(payload)

@pytest.mark.parametrize("lower,upper",[(-1,1),(3,2),(0,float("inf"))])
def test_resource_ranges_reject_invalid_bounds(lower,upper):
    with pytest.raises(ValidationError): NumericRange(lower=lower,upper=upper,unit="GPU-hours")

def test_resource_units_and_gpu_assumptions_are_explicit():
    payload=card_payload()["resources"]
    payload["wall_hours_range"]["unit"]="GPU-hours"
    with pytest.raises(ValidationError): ResourceEstimate.model_validate(payload)
    payload=card_payload()["resources"]; payload["gpu_count"]=0
    with pytest.raises(ValidationError): ResourceEstimate.model_validate(payload)
    payload=card_payload()["resources"]; payload["gpu_count"]="1"
    with pytest.raises(ValidationError): ResourceEstimate.model_validate(payload)

def test_reasonable_unperformed_experiment_can_be_promising_handoff():
    result=SelectorResult.model_validate(selection_payload())
    assert result.selection=="MAIN_REPORT" and result.next_action=="HANDOFF_EXPERIMENT"

def test_selection_contradiction_and_unexplained_rejection_fail():
    payload=selection_payload(); payload["assessment"]="REJECTED"
    with pytest.raises(ValidationError): SelectorResult.model_validate(payload)
    payload["selection"]="NOT_RETAINED"
    with pytest.raises(ValidationError): SelectorResult.model_validate(payload)

def test_next_draw_cannot_continue_just_because_quota_remains():
    with pytest.raises(ValidationError):
        NextDrawResult(continue_or_stop="CONTINUE",proposed_family=None,anchor_evidence_ids=[],distinct_from_retained=None,relevant_archive_relations=[],missing_information=[],why_this_draw_is_worthwhile=None)

def test_moderator_plain_stop_and_score_are_not_control_contract():
    with pytest.raises(ValidationError): ModeratorResult.model_validate({"text":"STOP; score=5"})

def test_subject_card_and_version_are_paired():
    with pytest.raises(ValidationError): Subject(campaign_id=None,run_id="r",card_id="c",card_version=None)

@pytest.mark.parametrize("action",["REASON","RETRIEVE"])
def test_moderator_action_requires_a_corresponding_unresolved_issue(action):
    with pytest.raises(ValidationError):
        ModeratorResult(assessment="NEEDS_EVIDENCE",next_action=action,stop_reason=None,concise_ruling="continue",issue_transitions=[],updated_issues=[],decisive_evidence_ids=[],proposed_card_revision=None,external_test_requirements=[],direction_change=None)

def test_reopening_boolean_alone_cannot_claim_new_evidence():
    from arc.schemas import ArchiveRelation
    payload={"archive_card_id":"fixture_card","archive_card_version":1,"relation":"reopening_candidate","rationale":"condition changed","reopening_condition_met":True}
    with pytest.raises(ValidationError): ArchiveRelation.model_validate(payload)
    payload.update(reopening_condition="new original result contradicts prior rejection",new_evidence_ids=["fixture_new_evidence"])
    assert ArchiveRelation.model_validate(payload).reopening_condition_met is True

def test_duplicate_claim_ids_and_non_object_candidates_are_protocol_errors():
    from arc.schemas import ComposeResult
    payload=card_payload()
    claim={"claim_id":"C1","version":1,"text":"synthetic claim","conditions":[],"kind":"hypothesis","evidence_ids":[]}
    payload["claims"]=[claim,dict(claim)]
    with pytest.raises(ValidationError): CardDraft.model_validate(payload)
    with pytest.raises(ValidationError): ComposeResult(card_candidate=["not a card"],composition_reason="bad structure",unresolved_prerequisites=[])
    assert ComposeResult(card_candidate=None,composition_reason="nothing worth retaining",unresolved_prerequisites=[]).card_candidate is None

def test_finding_target_claim_requires_paired_existing_reference_shape():
    from arc.schemas import Finding
    payload={"claim":"observation","conditions":[],"source_id":"fixture_source","locator":None,"locator_status":"locator_unverified","relation":"supports","origin":"original","excerpt":None,"support_explanation":"not yet verified"}
    assert Finding.model_validate(payload).claim_id is None
    with pytest.raises(ValidationError): Finding.model_validate({**payload,"claim_id":"C1"})
    with pytest.raises(ValidationError): Finding.model_validate({**payload,"claim_version":2})
    assert Finding.model_validate({**payload,"claim_id":"C1","claim_version":2}).claim_version==2
