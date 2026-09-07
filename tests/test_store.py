import json
from pathlib import Path
import pytest
from arc.store import Store, StateError
from arc.schemas import (CardDraft, SourceRecord, EvidenceRecord, TaskRecord, Issue,
    IssueTransition, DirectionChangeDraft, Finding)
from .test_contracts import card_payload, selection_payload

@pytest.fixture
def store(tmp_path):
    return Store(tmp_path/"arc.sqlite")

def source(store,*,original=True,source_id="fixture_source",content="Section 1\nA controlled observation.\nEnd."):
    return store.register_source(SourceRecord(source_id=source_id,title="Synthetic fixture material",url="https://example.test/paper",source_type="paper" if original else "secondary_analysis",access_status="retrieved",content_origin="original" if original else "secondary_analysis"),content=content)

def evidence(store,src,**updates):
    data=dict(evidence_id="fixture_evidence",source_id=src.source_id,claim_id="claim1",claim_version=1,claim="A controlled observation.",conditions=["synthetic"],locator="L2",excerpt="A controlled observation.",relation="motivates",origin="original",locator_status="verified",verification_status="verified",support_explanation="The exact passage supplies the observation; it does not prove the hypothesis.")
    data.update(updates)
    return store.register_evidence(EvidenceRecord(**data))

def test_draw_claims_are_atomic_idempotent_and_never_reset(store):
    campaign=store.create_campaign("arbitrary topic")
    assert store.claim_draw(campaign.campaign_id,"not_started",paid_admitted=False)==0
    for number in range(1,6):
        assert store.claim_draw(campaign.campaign_id,f"d{number}")==number
        assert store.claim_draw(campaign.campaign_id,f"d{number}")==number
    restarted=Store(store.db_path)
    assert restarted.get_campaign(campaign.campaign_id).draws_started==5
    with pytest.raises(StateError): restarted.claim_draw(campaign.campaign_id,"d6")
    with pytest.raises(StateError): store.update_campaign(campaign.campaign_id,draws_started=0)
    assert store.get_campaign(campaign.campaign_id).topic=="arbitrary topic"

def test_card_versions_are_immutable_and_idempotent_across_crash(store):
    card=store.save_card(CardDraft.model_validate(card_payload()),creation_key="compose-task")
    assert store.save_card(CardDraft.model_validate(card_payload()),creation_key="compose-task")==card
    revised=card.draft.model_copy(deep=True); revised.method.simplest_path="更简单的方法"
    next_card=store.save_card(revised,card_id=card.card_id,parent_version=1,creation_key="develop-task")
    assert next_card.version==2
    assert store.save_card(revised,card_id=card.card_id,parent_version=1,creation_key="develop-task").version==2
    assert store.get_card(card.card_id,1).draft.method.simplest_path!="更简单的方法"
    with pytest.raises(StateError): store.save_card(revised,card_id=card.card_id,parent_version=1)
    changed=card.draft.model_copy(deep=True); changed.problem_anchor.question="新问题"
    with pytest.raises(StateError): store.save_card(changed,card_id=card.card_id,parent_version=2)

def test_card_creation_can_atomically_update_run_pointer_and_state(store):
    run=store.create_run("discover")
    card=store.save_card(card_payload(),creation_key="task",run_id=run.run_id,state_patch={"compose_completed":True})
    assert store.get_run(run.run_id).card_id==card.card_id
    assert store.get_run(run.run_id).state["compose_completed"] is True
    assert len(store.list_cards(run_id=run.run_id))==1

def test_same_chinese_title_does_not_collide_and_archive_is_paginated(store):
    for _ in range(10): store.save_card(card_payload())
    result=store.lookup_archive("测量误差",limit=3)
    assert result["total"]==10 and len(result["records"])==3
    assert len({x["card_id"] for x in result["records"]})==3
    page=store.lookup_archive("测量误差",limit=3,offset=3)
    assert not {x["card_id"] for x in result["records"]}&{x["card_id"] for x in page["records"]}
    assert result["unsearched_limits"]
    assert store.lookup_archive("无匹配术语")['records']==[]

def test_source_mirrors_share_canonical_identity_not_independent_evidence(store):
    first=store.register_source(SourceRecord(title="paper",url="https://arxiv.org/abs/2601.00001",arxiv_id="2601.00001",source_type="paper",access_status="metadata_only",content_origin="metadata"))
    second=store.register_source(SourceRecord(title="same paper",url="https://arxiv.org/pdf/2601.00001.pdf",source_type="paper",access_status="metadata_only",content_origin="metadata"))
    assert first.source_id==second.source_id
    assert len(store.list_sources())==1
    payload=card_payload(); payload["closest_work_delta"]["source_ids"]=[first.source_id]
    card=store.save_card(payload)
    result=store.lookup_archive("arXiv:2601.00001v2")
    assert result["records"][0]["card_id"]==card.card_id

def test_source_access_and_provenance_survive_recovery(store):
    src=source(store)
    ev=evidence(store,src)
    restarted=Store(store.db_path)
    assert restarted.get_source(src.source_id)==src
    assert restarted.list_evidence(ids=[ev.evidence_id])==[ev]
    assert restarted.get_record(src.source_id)["content"].endswith("End.")
    assert restarted.list_sources(ids=[])==[]
    assert restarted.list_evidence(ids=[])==[]

def test_missing_or_invented_source_and_excerpt_are_rejected(store):
    with pytest.raises(StateError): store.register_source(SourceRecord(title="fake",url="not a URL",source_type="paper",access_status="metadata_only",content_origin="metadata"))
    src=source(store)
    with pytest.raises(StateError): evidence(store,src,source_id="hallucinated")
    with pytest.raises(StateError): evidence(store,src,excerpt="This was never returned.")
    with pytest.raises(StateError): evidence(store,src,locator="L99")
    with pytest.raises(StateError): evidence(store,src,locator="L1")
    with pytest.raises(StateError): store.validate_references({"evidence_ids":["invented"]})

def test_secondary_analysis_cannot_be_marked_original_or_verified(store):
    src=source(store,original=False)
    with pytest.raises(StateError): evidence(store,src)
    with pytest.raises(StateError): evidence(store,src,origin="secondary_analysis")
    ev=evidence(store,src,origin="secondary_analysis",verification_status="unverified",locator_status="locator_unverified")
    assert ev.verification_status=="unverified"

def test_changed_claim_cannot_reuse_previous_version_evidence(store):
    src=source(store); ev=evidence(store,src)
    payload=card_payload(); payload["claims"]=[{"claim_id":"claim1","version":1,"text":"A controlled observation.","conditions":["synthetic"],"kind":"empirical","evidence_ids":[ev.evidence_id]}]
    card=store.save_card(payload)
    revision=card.draft.model_copy(deep=True); revision.claims[0].text="A broader untested claim."
    with pytest.raises(StateError): store.save_card(revision,card_id=card.card_id,parent_version=1)
    revision.claims[0].version=2
    with pytest.raises(StateError): store.save_card(revision,card_id=card.card_id,parent_version=1)
    revision.claims[0].evidence_ids=[]
    assert store.save_card(revision,card_id=card.card_id,parent_version=1).version==2

def test_response_saved_survives_parse_failure_and_old_date(store):
    run=store.create_run("run")
    path=store.save_artifact("runs/raw.json",'{"body":"UNRESOLVED"}')
    task=TaskRecord(task_id="t",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m",status="RESPONSE_SAVED",response_artifact_path=path,created_at="2020-01-01T00:00:00+00:00")
    store.put_task(task)
    restored=Store(store.db_path).get_task("t")
    assert restored.status=="RESPONSE_SAVED" and restored.created_at.startswith("2020")
    assert json.loads(store.read_artifact(restored.response_artifact_path))["body"]=="UNRESOLVED"
    changed=restored.model_copy(update={"prompt_hash":"new"})
    with pytest.raises(StateError): store.put_task(changed)
    restored.accepted_result={"valid":True}; restored.status="ACCEPTED"; store.put_task(restored)
    restored.status="PENDING"
    with pytest.raises(StateError): store.put_task(restored)

def test_partial_artifact_cannot_be_accepted_and_paths_are_bounded(store):
    run=store.create_run("run")
    with pytest.raises(StateError): store.save_artifact("../escape.txt","private")
    with pytest.raises(StateError): store.put_task(TaskRecord(task_id="t",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m",status="ACCEPTED",accepted_result={"ok":True}))

def test_deep_stable_id_artifact_paths_work_without_title_truncation(store):
    relative="runs/"+"a"*64+"/tasks/"+"b"*64+"/requests/"+"c"*64+".json"
    saved=store.save_artifact(relative,'{"complete":true}')
    assert saved==relative and json.loads(store.read_artifact(saved))["complete"] is True

def test_issue_ledger_preserves_unseen_issues_and_validates_transitions(store):
    evidence(store,source(store),claim_id="C1")
    run=store.create_run("run")
    issue=Issue(issue_id="I1",claim_id="C1",claim_version=1,content="measurement unclear",status="open",evidence_ids=[],resolution_criterion="positive control",change_this_round="new",next_action="REASON")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="open",change_this_round="new",basis_evidence_ids=[],basis_argument=None,resolution_reason=None)
    store.apply_issues(run.run_id,[issue],[transition])
    with pytest.raises(StateError): store.apply_issues(run.run_id,[],[])
    closed=issue.model_copy(update={"status":"resolved"})
    closing=transition.model_copy(update={"from_status":"open","to_status":"resolved","basis_argument":"both agents agree"})
    with pytest.raises(StateError): store.apply_issues(run.run_id,[closed],[closing])
    assert Store(store.db_path).get_issues(run.run_id)[0].status=="open"
    assert store.get_issues(run.run_id)[0].resolution_criterion=="positive control"

def test_logical_issue_can_resolve_by_argument_but_reopen_requires_new_basis(store):
    evidence(store,source(store),claim_id="C1")
    run=store.create_run("run")
    issue=Issue(issue_id="I1",claim_id="C1",claim_version=1,content="definition",status="resolved",evidence_ids=[],resolution_criterion="definition",change_this_round="clarified",next_action="STOP",claim_kind="definition")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="resolved",change_this_round="clarified",basis_evidence_ids=[],basis_argument="The two terms share this explicit definition.",resolution_reason="definition established")
    store.apply_issues(run.run_id,[issue],[transition])
    issue.status="open"; transition.from_status="resolved"; transition.to_status="open"
    with pytest.raises(StateError): store.apply_issues(run.run_id,[issue],[transition])
    transition.new_evidence_or_argument="A new condition changes the definition."
    store.apply_issues(run.run_id,[issue],[transition])
    assert store.get_issues(run.run_id)[0].status=="open"

def test_empirical_issue_cannot_be_reclassified_to_bypass_evidence(store):
    evidence(store,source(store),claim_id="C1")
    run=store.create_run("run")
    issue=Issue(issue_id="I1",claim_id="C1",claim_version=1,content="empirical concern",status="open",evidence_ids=[],resolution_criterion="original evidence",change_this_round="new",next_action="REASON")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="open",change_this_round="new",basis_evidence_ids=[],basis_argument=None,resolution_reason=None)
    store.apply_issues(run.run_id,[issue],[transition],event_key="round1")
    changed=issue.model_copy(update={"claim_kind":"definition","status":"resolved"})
    closing=transition.model_copy(update={"from_status":"open","to_status":"resolved","basis_argument":"agreed definition"})
    with pytest.raises(StateError,match="kind_changed"):
        store.apply_issues(run.run_id,[changed],[closing],event_key="round2")
    restarted=Store(store.db_path)
    assert restarted.apply_issues(run.run_id,[issue],[transition],event_key="round1")[0].issue_id=="I1"
    assert restarted.get_issues(run.run_id)[0].status=="open"

def test_claim_version_cannot_regress_or_reclassify_without_new_version(store):
    payload=card_payload()
    payload["claims"]=[{"claim_id":"C1","version":2,"text":"observation","conditions":[],"kind":"empirical","evidence_ids":[]}]
    card=store.save_card(payload)
    revision=card.draft.model_copy(deep=True); revision.claims[0].version=1
    with pytest.raises(StateError,match="regress"):
        store.save_card(revision,card_id=card.card_id,parent_version=1)
    revision.claims[0].version=2; revision.claims[0].kind="definition"
    with pytest.raises(StateError,match="new_version"):
        store.save_card(revision,card_id=card.card_id,parent_version=1)
    revision.claims[0].version=3
    assert store.save_card(revision,card_id=card.card_id,parent_version=1).version==2

def test_selection_does_not_rewrite_card_and_is_unique_for_version(store):
    card=store.save_card(card_payload()); run=store.create_run("discover")
    selected=store.record_selection(run.run_id,card.card_id,1,selection_payload(),state_patch={"draws":{"draw1":{"finished":True}}})
    assert selected.draft==card.draft and selected.selection_result is not None
    assert selected.selection=="MAIN_REPORT"
    assert store.get_run(run.run_id).state["draws"]["draw1"]["finished"] is True
    changed=selection_payload(); changed["why_worth_investigating"]="different judgment"
    with pytest.raises(StateError): store.record_selection(run.run_id,card.card_id,1,changed)

def test_direction_change_is_single_frozen_event_and_restart_uses_new_campaign(store):
    src=source(store); ev=evidence(store,src)
    payload=card_payload(); payload["closest_work_delta"]["source_ids"]=[src.source_id]
    card=store.save_card(payload); run=store.create_run("develop",card_id=card.card_id,card_version=1)
    anchor=card.draft.problem_anchor.model_copy(update={"question":"真正新问题"})
    change=DirectionChangeDraft(proposed_problem_anchor=anchor,trigger_evidence_ids=[ev.evidence_id],original_sources_revisited=[src.source_id],missed_evidence_analysis="Earlier reading omitted the condition.")
    event=store.save_direction_change(run.run_id,change,original_audit={"source_ids":[src.source_id]})
    assert event.status=="FROZEN" and store.get_run(run.run_id).status=="PAUSED_SCOPE_CHANGE"
    assert store.save_direction_change(run.run_id,change,original_audit={"source_ids":[src.source_id]}).direction_change_id==event.direction_change_id
    other=change.model_copy(deep=True); other.proposed_problem_anchor.question="另一个问题"
    with pytest.raises(StateError): store.save_direction_change(run.run_id,other,original_audit={"source_ids":[src.source_id]})
    changed_basis=change.model_copy(update={"missed_evidence_analysis":"different explanation"})
    with pytest.raises(StateError): store.save_direction_change(run.run_id,changed_basis,original_audit={"source_ids":[src.source_id]})
    campaign=store.create_campaign("approved new seed",parent_card_id=card.card_id,parent_card_version=1)
    assert campaign.draws_started==0 and campaign.parent_card_id==card.card_id

def test_scope_audit_cannot_treat_secondary_text_as_original(store):
    src=source(store,original=False)
    ev=evidence(store,src,origin="secondary_analysis",verification_status="unverified",locator_status="locator_unverified")
    payload=card_payload(); payload["closest_work_delta"]["source_ids"]=[src.source_id]
    card=store.save_card(payload); run=store.create_run("develop",card_id=card.card_id,card_version=1)
    change=DirectionChangeDraft(proposed_problem_anchor=card.draft.problem_anchor.model_copy(update={"question":"new question"}),trigger_evidence_ids=[ev.evidence_id],original_sources_revisited=[src.source_id],missed_evidence_analysis="Generated summary asserted an omission.")
    with pytest.raises(StateError,match="returned_original"):
        store.save_direction_change(run.run_id,change,original_audit={"source_ids":[src.source_id]})
    assert store.get_scope_changes(run.run_id)==[]

def test_findings_register_only_actual_returned_passages_and_are_idempotent(store):
    src=source(store); run=store.create_run("discover")
    task=TaskRecord(task_id="find",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m")
    store.put_task(task)
    finding=Finding(claim="A controlled observation.",conditions=[],source_id=src.source_id,locator="L2",locator_status="verified",relation="motivates",origin="original",excerpt="A controlled observation.",support_explanation="Exact original observation.")
    records=store.register_findings([finding],"find")
    assert records[0].verification_status=="verified"
    assert store.register_findings([finding],"find")==records
    finding.excerpt="not returned"
    with pytest.raises(StateError): store.register_findings([finding],"find")

def test_finding_locator_is_derived_from_original_not_invented_page(store):
    src=source(store)
    run=store.create_run("discover")
    store.put_task(TaskRecord(task_id="locate",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="A controlled observation.",conditions=[],source_id=src.source_id,locator="Page 99 Section 99",locator_status="verified",relation="motivates",origin="original",excerpt="A controlled observation.",support_explanation="Model interpretation, not a proof of support.")
    record=store.register_findings([finding],"locate")[0]
    assert record.locator=="chars:10:35"
    assert record.locator_status=="verified"
    assert finding.locator=="Page 99 Section 99"
    with pytest.raises(StateError,match="checkable_range"):
        evidence(store,src,locator="Section 1")
    with pytest.raises(StateError): evidence(store,src,locator="Page 99")
    with pytest.raises(StateError): evidence(store,src,locator="chars:0:9")

def test_repeated_finding_excerpt_remains_locator_unverified(store):
    src=source(store,content="A controlled observation.\nOpposite setting\nA controlled observation.")
    run=store.create_run("discover")
    store.put_task(TaskRecord(task_id="repeat",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="A controlled observation.",conditions=[],source_id=src.source_id,locator="Sec 99",locator_status="verified",relation="motivates",origin="original",excerpt="A controlled observation.",support_explanation="Ambiguous repeated text.")
    record=store.register_findings([finding],"repeat")[0]
    assert record.locator is None
    assert record.locator_status=="locator_unverified"
    assert record.verification_status=="unverified"

def test_issue_event_replay_and_round_checkpoint_are_one_transaction(store):
    evidence(store,source(store),claim_id="C1")
    run=store.create_run("run")
    issue=Issue(issue_id="I1",claim_id="C1",claim_version=1,content="open concern",status="open",evidence_ids=[],resolution_criterion="evidence",change_this_round="new",next_action="REASON")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="open",change_this_round="new",basis_evidence_ids=[],basis_argument=None,resolution_reason=None)
    for _ in range(2):
        store.apply_issues(run.run_id,[issue],[transition],event_key="round1",state_patch={"rounds_completed":1})
    assert store.get_run(run.run_id).state["rounds_completed"]==1
    assert len(store.get_issues(run.run_id))==1
    with pytest.raises(StateError): store.apply_issues(run.run_id,[issue],[transition],event_key="round1",state_patch={"rounds_completed":2})
    unknown=issue.model_copy(update={"issue_id":"I2","claim_id":"invented"})
    t2=transition.model_copy(update={"issue_id":"I2"})
    retained=transition.model_copy(update={"from_status":"open"})
    with pytest.raises(StateError): store.apply_issues(run.run_id,[issue,unknown],[retained,t2],event_key="round2",state_patch={"rounds_completed":2})
    assert store.get_run(run.run_id).state["rounds_completed"]==1

def test_empirical_resolution_needs_verified_matching_evidence(store):
    src=source(store); ev=evidence(store,src,relation="supports")
    run=store.create_run("run")
    issue=Issue(issue_id="I1",claim_id="claim1",claim_version=1,content="empirical concern",status="resolved",evidence_ids=[ev.evidence_id],resolution_criterion="original evidence",change_this_round="supported",next_action="STOP")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="resolved",change_this_round="supported",basis_evidence_ids=[ev.evidence_id],basis_argument=None,resolution_reason="original evidence answers this claim")
    store.apply_issues(run.run_id,[issue],[transition])
    assert store.get_issues(run.run_id)[0].status=="resolved"

def test_targeted_finding_resolves_existing_second_version_claim(store):
    src=source(store)
    payload=card_payload()
    payload["claims"]=[{"claim_id":"C1","version":2,"text":"Target empirical claim","conditions":["controlled setting"],"kind":"empirical","evidence_ids":[]}]
    card=store.save_card(payload); run=store.create_run("run",card_id=card.card_id,card_version=1)
    store.put_task(TaskRecord(task_id="targeted",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="A controlled observation.",claim_id="C1",claim_version=2,conditions=["controlled setting"],source_id=src.source_id,locator=None,locator_status="locator_unverified",relation="supports",origin="original",excerpt="A controlled observation.",support_explanation="The model judged this observation relevant to C1 under the stated conditions.")
    ev=store.register_findings([finding],"targeted",allowed_claims=card.draft.claims)[0]
    assert (ev.claim_id,ev.claim_version)==("C1",2)
    assert Store(store.db_path).register_findings([finding],"targeted")[0]==ev
    issue=Issue(issue_id="I1",claim_id="C1",claim_version=2,content="empirical concern",status="resolved",evidence_ids=[ev.evidence_id],resolution_criterion="original evidence",change_this_round="supported",next_action="STOP")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="resolved",change_this_round="supported",basis_evidence_ids=[ev.evidence_id],basis_argument=None,resolution_reason="Explicitly targeted original evidence.")
    store.apply_issues(run.run_id,[issue],[transition],event_key="targeted-round")
    assert store.get_issues(run.run_id)[0].status=="resolved"
    for updates in ({"claim_id":"invented"},{"claim_version":1}):
        with pytest.raises(StateError,match="current_input"):
            store.register_findings([finding.model_copy(update=updates)],"targeted")

def test_new_observation_claim_identity_includes_conditions(store):
    src=source(store); run=store.create_run("discover")
    store.put_task(TaskRecord(task_id="conditions",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="A controlled observation.",conditions=["setting A"],source_id=src.source_id,locator=None,locator_status="locator_unverified",relation="motivates",origin="original",excerpt="A controlled observation.",support_explanation="Original observation with stated condition.")
    records=store.register_findings([finding,finding.model_copy(update={"conditions":["setting B"]})],"conditions")
    assert records[0].claim_id!=records[1].claim_id

def test_versioned_arxiv_cache_restores_same_explicit_version(store):
    first=store.register_source(SourceRecord(title="versioned synthetic paper",url="https://arxiv.org/html/2601.00001v2",source_type="paper",access_status="metadata_only",content_origin="metadata"))
    assert first.arxiv_id=="2601.00001v2" and first.version=="2"
    second=store.register_source(SourceRecord(title="same version",url="https://arxiv.org/pdf/2601.00001v2.pdf",arxiv_id="2601.00001v2",version="2601.00001v2",source_type="paper",access_status="metadata_only",content_origin="metadata"))
    assert Store(store.db_path).get_source(first.source_id)==first
    assert second.source_id==first.source_id and second.version=="2"

def test_capability_request_returns_durable_real_record_id(store):
    run=store.create_run("discover")
    request={"blocked_question":"Can original text be accessed?","needed_operation":"read_original","input_fields":["source_id"],"required_output":"original text","provenance_needs":"exact locator","cost_visibility_needs":"upper bound","acceptance_example":"fixture original passage"}
    identifier=store.save_capability_request(run.run_id,request)
    assert identifier.startswith("cap_")
    assert Store(store.db_path).get_record(identifier)["needed_operation"]=="read_original"
    assert store.list_capability_requests(run.run_id)[0]["request_id"]==identifier

def test_full_original_preserves_decisive_condition_at_long_document_end(store):
    content=("irrelevant contextual detail "*6000)+"\nDECISIVE: the measurement only applies under condition Z."
    src=source(store,content=content)
    recovered=Store(store.db_path).get_record(src.source_id)["content"]
    assert recovered==content and recovered.endswith("condition Z.")
    with pytest.raises(StateError): store.validate_references({"new_evidence_ids":["hallucinated_reopening"]})

def test_same_representation_partial_source_upgrades_without_losing_evidence(store):
    full="Section 1\nA controlled observation.\nMore original text."
    prefix=full[:35]
    record=SourceRecord(title="original",url="https://example.test/paper",source_type="paper",access_status="retrieved",content_origin="original",content_complete=False,content_total_chars=len(full),representation_id="service:extractor:htmlhash")
    first=store.register_source(record,content=prefix)
    ev=evidence(store,first)
    upgraded=store.register_source(record.model_copy(update={"source_id":"another_source","content_complete":True}),content=full)
    assert upgraded.source_id==first.source_id and upgraded.content_complete is True
    assert store.read_artifact(first.content_path)==prefix
    assert store.get_record(first.source_id)["content"]==full
    assert store.list_evidence(ids=[ev.evidence_id])==[ev]
    assert store.register_evidence(ev)==ev

@pytest.mark.parametrize("change",["different_representation","different_prefix","complete_conflict"])
def test_source_extension_rejects_unproven_or_conflicting_content(store,change):
    old="original prefix"; full=old+" longer"
    record=SourceRecord(title="original",url="https://example.test/paper",source_type="paper",access_status="retrieved",content_origin="original",content_complete=change=="complete_conflict",content_total_chars=len(old) if change=="complete_conflict" else len(full),representation_id="service:extractor:hash1")
    first=store.register_source(record,content=old)
    incoming=record.model_copy(update={"source_id":"other","content_complete":True,"content_total_chars":len(full)})
    if change=="different_representation": incoming.representation_id="service:extractor:hash2"
    if change=="different_prefix": full="contrary prefix longer"; incoming.content_total_chars=len(full)
    with pytest.raises(StateError,match="explicit_version"):
        store.register_source(incoming,content=full)
    assert store.get_record(first.source_id)["content"]==old
