import json
from pathlib import Path
import pytest
from arc.store import Store, StateError, claim_fingerprint
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
    assert ev.target_claim_fingerprint==claim_fingerprint(card.draft.claims[0])
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

@pytest.mark.parametrize("change",["different_prefix","complete_conflict"])
def test_source_extension_rejects_unproven_or_conflicting_content(store,change):
    old="original prefix"; full=old+" longer"
    record=SourceRecord(title="original",url="https://example.test/paper",source_type="paper",access_status="retrieved",content_origin="original",content_complete=change=="complete_conflict",content_total_chars=len(old) if change=="complete_conflict" else len(full),representation_id="service:extractor:hash1")
    first=store.register_source(record,content=old)
    incoming=record.model_copy(update={"source_id":"other","content_complete":True,"content_total_chars":len(full)})
    if change=="different_prefix": full="contrary prefix longer"; incoming.content_total_chars=len(full)
    with pytest.raises(StateError,match="explicit_version"):
        store.register_source(incoming,content=full)
    assert store.get_record(first.source_id)["content"]==old

def test_paper_landing_page_and_body_have_distinct_representations_not_independent_works(store):
    landing="Submission history\nAbstract only.\nWebsite footer"
    body="Paper title\nMethods and experiments of the paper."
    first=store.register_source(SourceRecord(title="paper",url="https://arxiv.org/abs/2306.16132",source_type="paper",access_status="retrieved",content_origin="original",content_complete=True,content_total_chars=len(landing),representation_id="webresearch:trafilatura:landing_hash"),content=landing)
    old_evidence=store.register_evidence(EvidenceRecord(source_id=first.source_id,claim_id="claim_landing",claim_version=1,claim="Abstract statement",conditions=[],locator="L2",excerpt="Abstract only.",relation="motivates",origin="original",locator_status="verified",verification_status="verified",support_explanation="Exact abstract text; scope remains the abstract."))
    second=store.register_source(SourceRecord(title="paper",url="https://ar5iv.labs.arxiv.org/html/2306.16132",arxiv_id="2306.16132",source_type="paper",access_status="retrieved",content_origin="original",content_complete=True,content_total_chars=len(body),representation_id="webresearch:trafilatura:body_hash"),content=body)
    assert first.source_id!=second.source_id
    assert first.canonical_id==second.canonical_id=="arxiv:2306.16132"
    assert len({item.canonical_id for item in store.list_sources()})==1
    assert store.get_record(first.source_id)["content"]==landing
    assert store.get_record(second.source_id)["content"]==body
    assert store.register_evidence(old_evidence)==old_evidence
    assert store.register_source(second.model_copy(update={"source_id":"mirror"}),content=body).source_id==second.source_id
    with pytest.raises(StateError,match="explicit_version"):
        store.register_source(second.model_copy(update={"content_total_chars":len("conflicting original")}),content="conflicting original")

@pytest.mark.parametrize("complete",[True,False])
@pytest.mark.parametrize("same_length",[True,False])
def test_shorter_same_representation_reuses_longer_registered_source(store,complete,same_length):
    full="original prefix and more original content"
    old=full if complete else full[:25]
    incoming_text=old if same_length else old[:15]
    record=SourceRecord(title="original",url="https://example.test/paper",source_type="paper",access_status="retrieved",content_origin="original",content_complete=complete,content_total_chars=len(full),representation_id="service:extractor:samehash")
    first=store.register_source(record,content=old)
    incoming=record.model_copy(update={"source_id":"short_read","content_complete":False,"content_path":None,"content_sha256":None})
    restored=store.register_source(incoming,content=incoming_text)
    assert restored==first
    assert store.get_record(first.source_id)["content"]==old
    assert restored.content_complete is complete
    assert incoming.content_complete is False
    assert store.read_artifact(incoming.content_path)==incoming_text

def test_card_provenance_inherits_only_linked_version_research_inputs(store):
    src=source(store); ev=evidence(store,src,relation="challenges")
    campaign=store.create_campaign("specific scope")
    prior=store.create_run("discover",campaign_id=campaign.campaign_id,state={"source_ids":[src.source_id],"evidence_ids":[ev.evidence_id],"assessment":"PROMISING","rounds_completed":9})
    card=store.save_card(card_payload(),run_id=prior.run_id)
    assert card.draft.motivation.evidence_ids==[]
    investigation={"questions_addressed":["What contradicts this idea?"],"actual_searches":[],"findings":[],"contrary_findings":[],"source_access_limits":["missing appendix"],"implications_for_current_card":["uncertain"],"unresolved_questions":["unresolved condition"],"recommended_next_action":"RETRIEVE"}
    response=store.save_artifact("test/investigation.json",json.dumps(investigation))
    store.put_task(TaskRecord(task_id="original-investigation",run_id=prior.run_id,input_hash="i",prompt_hash="p",model_config_hash="m",status="ACCEPTED",response_artifact_path=response,prompt_manifest={"roles/investigator.md":"fixture_sha256"},accepted_result={"result":investigation}))
    store.put_task(TaskRecord(task_id="name-claims-investigator-but-is-not",run_id=prior.run_id,input_hash="i",prompt_hash="p",model_config_hash="m",status="ACCEPTED",response_artifact_path=response,prompt_manifest={"roles/selector.md":"fixture_sha256"},accepted_result={"result":investigation}))
    unrelated_source=store.register_source(SourceRecord(title="unrelated",url="https://unrelated.test/paper",source_type="paper",access_status="metadata_only",content_origin="metadata"))
    unrelated=store.create_run("discover",state={"source_ids":[unrelated_source.source_id]})
    store.save_card(card_payload(),run_id=unrelated.run_id)
    revision=store.save_card(card.draft,card_id=card.card_id,parent_version=1)
    later=store.create_run("develop",card_id=card.card_id,card_version=revision.version,state={"source_ids":[unrelated_source.source_id]})
    context=store.card_provenance_context(card.card_id,1)
    assert context["source_ids"]==[src.source_id]
    assert context["evidence_ids"]==[ev.evidence_id]
    assert context["provenance_run_ids"]==[prior.run_id]
    assert context["provenance_campaign_ids"]==[campaign.campaign_id]
    assert context["investigation_task_ids"]==["original-investigation"]
    original_record=store.get_record("original-investigation")
    assert original_record["accepted_result"]["result"]["unresolved_questions"]==["unresolved condition"]
    assert set(original_record)=={"task_id","run_id","status","accepted_result","evidence_ids"}
    assert set(context)=={"card_id","card_version","source_ids","evidence_ids","provenance_run_ids","provenance_campaign_ids","investigation_task_ids"}
    assert store.get_run(later.run_id).state=={"source_ids":[unrelated_source.source_id]}

def test_imported_card_provenance_is_empty_without_prior_runs(store):
    card=store.save_card(card_payload())
    context=store.card_provenance_context(card.card_id,1)
    assert context["provenance_run_ids"]==[]
    assert context["investigation_task_ids"]==[]
    assert context["evidence_ids"]==[]

def test_read_record_supports_campaign_run_and_scoped_issue_without_raw_state(store):
    src=source(store); ev=evidence(store,src,claim_id="C1")
    campaign=store.create_campaign("Original campaign",boundaries=["fixed scope"])
    run=store.create_run("discover",campaign_id=campaign.campaign_id,state={"evidence_ids":[ev.evidence_id],"task_inputs":{"raw_reasoning":"must not expose"},"private_checkpoint":"must not expose"})
    issue=Issue(issue_id="I1",claim_id="C1",claim_version=1,content="unresolved concern",status="open",evidence_ids=[ev.evidence_id],resolution_criterion="check original",change_this_round="new",next_action="REASON")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="open",change_this_round="new",basis_evidence_ids=[],basis_argument=None,resolution_reason=None)
    store.apply_issues(run.run_id,[issue],[transition])
    assert store.get_record(campaign.campaign_id)==campaign.model_dump(mode="json")
    readable=store.get_record(run.run_id)
    assert readable["source_ids"]==[src.source_id]
    assert readable["evidence_ids"]==[ev.evidence_id]
    assert readable["issues"]==[issue.model_dump(mode="json")]
    assert "task_inputs" not in readable and "state" not in readable
    assert "must not expose" not in json.dumps(readable)
    assert store.get_record("I1")=={"run_id":run.run_id,**issue.model_dump(mode="json")}
    other=store.create_run("run")
    second=issue.model_copy(update={"content":"different run concern"})
    store.apply_issues(other.run_id,[second],[transition])
    with pytest.raises(StateError,match="ambiguous"):
        store.get_record("I1")
    assert store.get_record("I1",run_id=run.run_id)["content"]=="unresolved concern"
    assert store.get_record("I1",run_id=other.run_id)["content"]=="different run concern"
    with pytest.raises(StateError,match="^record_missing$"):
        store.get_record("I1",run_id="not_this_run")

def test_read_record_unknown_ids_and_versions_have_one_missing_error(store):
    card=store.save_card(card_payload())
    assert store.get_record(card.card_id,1)["card_id"]==card.card_id
    for identifier,version in (("campaign_missing",None),("run_missing",None),("issue_missing",None),("anything",None),(card.card_id,999)):
        with pytest.raises(StateError,match="^record_missing$"):
            store.get_record(identifier,version)

def test_finding_prevalidation_is_read_only_and_batch_registration_is_all_or_nothing(store):
    src=source(store); run=store.create_run("discover")
    store.put_task(TaskRecord(task_id="batch",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    first=Finding(claim="A controlled observation.",conditions=[],source_id=src.source_id,locator=None,locator_status="locator_unverified",relation="motivates",origin="original",excerpt="A controlled observation.",support_explanation="Exact source text.")
    second=first.model_copy(update={"excerpt":"A controlled...observation."})
    prepared=store.validate_findings([first],"batch")
    assert len(prepared)==1 and store.list_evidence()==[]
    with pytest.raises(StateError,match="excerpt_not_in_returned_source") as error:
        store.validate_findings([first,second],"batch")
    assert str(error.value)=="excerpt_not_in_returned_source"
    assert error.value.__notes__==[f"finding[1] source_id={src.source_id}"]
    with pytest.raises(StateError,match="excerpt_not_in_returned_source"):
        store.register_findings([first,second],"batch")
    assert store.list_evidence()==[]
    assert store.get_task("batch").status=="PENDING"
    assert store.register_findings([first],"batch")[0].excerpt==first.excerpt

def test_finding_prevalidation_rejects_search_snippet_as_unread_original(store):
    src=store.register_source(SourceRecord(title="snippet metadata",url="https://example.test/snippet",source_type="paper",access_status="metadata_only",content_origin="metadata"))
    run=store.create_run("discover")
    store.put_task(TaskRecord(task_id="snippet",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="Search result claim",conditions=[],source_id=src.source_id,locator=None,locator_status="source_unavailable",relation="motivates",origin="original",excerpt="Words in search snippet but no registered original.",support_explanation="Cannot substitute a snippet for original evidence.")
    with pytest.raises(StateError,match="excerpt_not_in_returned_source"):
        store.validate_finding_sources([finding])
    with pytest.raises(StateError,match="excerpt_not_in_returned_source"):
        store.validate_findings([finding],"snippet")
    assert store.list_evidence()==[]

def test_new_card_claim_can_cite_background_without_transferring_verification(store):
    ev=evidence(store,source(store),relation="supports")
    original_evidence=ev.model_dump(mode="json")
    payload=card_payload()
    payload["claims"]=[{"claim_id":"new_synthesis","version":1,"text":"A new empirical synthesis to check.","conditions":["new condition"],"kind":"empirical","evidence_ids":[ev.evidence_id]}]
    card=store.save_card(payload)
    assert card.draft.model_dump()==CardDraft.model_validate(payload).model_dump()
    bindings=store.claim_evidence_bindings(card.draft)
    assert bindings==[{"claim_id":"new_synthesis","claim_version":1,
        "evidence_id":ev.evidence_id,"evidence_claim_id":ev.claim_id,"evidence_claim_version":1,
        "source_id":ev.source_id,"binding":"background_premise","relation":"supports",
        "evidence_verification_status":"verified","verification_transferred":False}]
    assert store.list_evidence(ids=[ev.evidence_id])[0].model_dump(mode="json")==original_evidence
    run=store.create_run("run",card_id=card.card_id,card_version=card.version)
    issue=Issue(issue_id="new_issue",claim_id="new_synthesis",claim_version=1,content="Does the new claim hold?",status="resolved",evidence_ids=[ev.evidence_id],resolution_criterion="Evidence for this claim under new conditions",change_this_round="claimed support",next_action="STOP")
    transition=IssueTransition(issue_id="new_issue",from_status=None,to_status="resolved",change_this_round="claimed support",basis_evidence_ids=[ev.evidence_id],basis_argument=None,resolution_reason="Background is asserted as proof.")
    with pytest.raises(StateError,match="empirical_resolution_requires_verified_claim_evidence"):
        store.apply_issues(run.run_id,[issue],[transition])
    assert store.get_issues(run.run_id)==[]

def test_target_binding_is_direction_not_proof_and_rejects_old_version(store):
    payload=card_payload()
    payload["claims"]=[{"claim_id":"claim1","version":1,"text":"A controlled observation.","conditions":["synthetic"],"kind":"empirical","evidence_ids":["fixture_evidence"]}]
    ev=evidence(store,source(store),relation="supports",target_claim_fingerprint=claim_fingerprint(payload["claims"][0]))
    card=store.save_card(payload)
    binding=store.claim_evidence_bindings(card.draft)[0]
    assert binding["binding"]=="current_claim_target"
    assert binding["verification_transferred"] is False
    revised=card.draft.model_copy(deep=True)
    revised.claims[0].version=2
    revised.claims[0].conditions=["changed condition"]
    with pytest.raises(StateError,match="claim_evidence_version_mismatch"):
        store.claim_evidence_bindings(revised)
    with pytest.raises(StateError,match="claim_evidence_version_mismatch"):
        store.save_card(revised,card_id=card.card_id,parent_version=1)

def test_claim_fingerprint_tracks_content_but_not_evidence_links():
    from arc.schemas import Claim
    claim=Claim(claim_id="C1",version=1,text="One claim",conditions=["condition A"],kind="empirical",evidence_ids=[])
    fingerprint=claim_fingerprint(claim)
    assert fingerprint==claim_fingerprint(claim.model_copy(update={"evidence_ids":["different link"]}))
    for update in ({"claim_id":"C2"},{"version":2},{"text":"Other claim"},{"conditions":["condition B"]},{"kind":"hypothesis"}):
        assert claim_fingerprint(claim.model_copy(update=update))!=fingerprint

def test_same_named_claims_on_different_cards_cannot_transfer_target_evidence(store):
    src=source(store)
    cards=[]; runs=[]
    for label in ("A","B"):
        payload=card_payload()
        payload["claims"]=[{"claim_id":"C1","version":1,"text":f"Claim from card {label}","conditions":[f"setting {label}"],"kind":"empirical","evidence_ids":[]}]
        card=store.save_card(payload); cards.append(card)
        run=store.create_run("run",card_id=card.card_id,card_version=card.version); runs.append(run)
        store.put_task(TaskRecord(task_id=f"target-{label}",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="A controlled observation.",claim_id="C1",claim_version=1,conditions=["observed setting"],source_id=src.source_id,locator=None,locator_status="locator_unverified",relation="supports",origin="original",excerpt="A controlled observation.",support_explanation="Model judgment about this explicit target, not a proof.")
    ev_a=store.register_findings([finding],"target-A",allowed_claims=cards[0].draft.claims)[0]
    original=ev_a.model_dump()
    for card,expected in zip(cards,("current_claim_target","background_premise")):
        draft=card.draft.model_copy(deep=True); draft.claims[0].evidence_ids=[ev_a.evidence_id]
        binding=store.claim_evidence_bindings(draft)[0]
        assert binding["binding"]==expected and binding["verification_transferred"] is False
    assert store.list_evidence(ids=[ev_a.evidence_id])[0].model_dump()==original
    with pytest.raises(StateError,match="finding_allowed_claim_not_registered_for_run"):
        store.register_findings([finding],"target-B",allowed_claims=cards[0].draft.claims)
    issue=Issue(issue_id="I1",claim_id="C1",claim_version=1,content="Does B hold?",status="resolved",evidence_ids=[ev_a.evidence_id],resolution_criterion="Evidence directed at B",change_this_round="claimed support",next_action="STOP")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="resolved",change_this_round="claimed support",basis_evidence_ids=[ev_a.evidence_id],basis_argument=None,resolution_reason="Explicitly targeted original evidence.")
    with pytest.raises(StateError,match="empirical_resolution_requires_verified_claim_evidence"):
        store.apply_issues(runs[1].run_id,[issue],[transition])
    assert store.get_issues(runs[1].run_id)==[]
    ev_b=store.register_findings([finding],"target-B",allowed_claims=cards[1].draft.claims)[0]
    assert ev_b.target_claim_fingerprint!=ev_a.target_claim_fingerprint
    issue.evidence_ids=[ev_b.evidence_id]; transition.basis_evidence_ids=[ev_b.evidence_id]
    store.apply_issues(runs[1].run_id,[issue],[transition])
    assert store.get_issues(runs[1].run_id)[0].status=="resolved"

def test_unbound_observation_does_not_gain_target_identity_from_matching_id(store):
    src=source(store); run=store.create_run("discover")
    store.put_task(TaskRecord(task_id="unbound",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="A controlled observation.",conditions=["synthetic"],source_id=src.source_id,locator=None,locator_status="locator_unverified",relation="supports",origin="original",excerpt="A controlled observation.",support_explanation="Original observation only.")
    ev=store.register_findings([finding],"unbound")[0]
    assert ev.target_claim_fingerprint is None
    payload=card_payload(); payload["claims"]=[{"claim_id":ev.claim_id,"version":1,"text":ev.claim,"conditions":ev.conditions,"kind":"empirical","evidence_ids":[ev.evidence_id]}]
    card=store.save_card(payload)
    assert store.claim_evidence_bindings(card.draft)[0]["binding"]=="background_premise"
    target_run=store.create_run("run",card_id=card.card_id,card_version=card.version)
    issue=Issue(issue_id="I1",claim_id=ev.claim_id,claim_version=1,content="Does the card claim hold?",status="resolved",evidence_ids=[ev.evidence_id],resolution_criterion="Explicit target evidence",change_this_round="claimed support",next_action="STOP")
    transition=IssueTransition(issue_id="I1",from_status=None,to_status="resolved",change_this_round="claimed support",basis_evidence_ids=[ev.evidence_id],basis_argument=None,resolution_reason="Same named observation is insufficient.")
    with pytest.raises(StateError,match="empirical_resolution_requires_verified_claim_evidence"):
        store.apply_issues(target_run.run_id,[issue],[transition])
    assert store.list_evidence(ids=[ev.evidence_id])[0].target_claim_fingerprint is None

def test_old_issue_resolution_uses_only_same_card_run_linked_claim_history(store):
    src=source(store)
    payload=card_payload()
    payload["claims"]=[{"claim_id":"C1","version":1,"text":"Original card claim","conditions":["condition A"],"kind":"empirical","evidence_ids":[]}]
    card=store.save_card(payload)
    run=store.create_run("run",card_id=card.card_id,card_version=1)
    store.put_task(TaskRecord(task_id="historic-target",run_id=run.run_id,input_hash="i",prompt_hash="p",model_config_hash="m"))
    finding=Finding(claim="A controlled observation.",claim_id="C1",claim_version=1,conditions=["condition A"],source_id=src.source_id,locator=None,locator_status="locator_unverified",relation="supports",origin="original",excerpt="A controlled observation.",support_explanation="Directed at the original card claim.")
    original_ev=store.register_findings([finding],"historic-target")[0]
    other_payload=card_payload()
    other_payload["claims"]=[{**payload["claims"][0],"text":"Other card claim"}]
    other_card=store.save_card(other_payload)
    other_ev=evidence(store,src,evidence_id="other-card-evidence",claim_id="C1",relation="supports",target_claim_fingerprint=claim_fingerprint(other_card.draft.claims[0]))
    issue=Issue(issue_id="old-I1",claim_id="C1",claim_version=1,content="Does the original claim hold?",status="open",evidence_ids=[],resolution_criterion="Original claim evidence",change_this_round="raised",next_action="REASON")
    opening=IssueTransition(issue_id=issue.issue_id,from_status=None,to_status="open",change_this_round="raised",basis_evidence_ids=[],basis_argument=None,resolution_reason=None)
    store.apply_issues(run.run_id,[issue],[opening])
    revised=card.draft.model_copy(deep=True); revised.claims[0].version=2; revised.claims[0].text="Revised card claim"
    current=store.save_card(revised,card_id=card.card_id,parent_version=1,run_id=run.run_id)
    store.update_run(run.run_id,card_id=current.card_id,card_version=current.version)
    store.link_card(run.run_id,other_card.card_id,other_card.version)
    issue.status="resolved"; issue.evidence_ids=[other_ev.evidence_id]
    resolving=IssueTransition(issue_id=issue.issue_id,from_status="open",to_status="resolved",change_this_round="checked",basis_evidence_ids=[other_ev.evidence_id],basis_argument=None,resolution_reason="Original claim only.")
    with pytest.raises(StateError,match="empirical_resolution_requires_verified_claim_evidence"):
        store.apply_issues(run.run_id,[issue],[resolving])
    assert store.get_issues(run.run_id)[0].status=="open"
    issue.evidence_ids=[original_ev.evidence_id]; resolving.basis_evidence_ids=[original_ev.evidence_id]
    store.apply_issues(run.run_id,[issue],[resolving])
    assert store.get_issues(run.run_id)[0].claim_version==1
    assert store.get_card(current.card_id,current.version).draft.claims[0].evidence_ids==[]
    # A fresh run attached only to v2 must not borrow an unlinked v1 record.
    unlinked_run=store.create_run("run",card_id=current.card_id,card_version=current.version)
    resolving.from_status=None
    with pytest.raises(StateError,match="empirical_resolution_requires_verified_claim_evidence"):
        store.apply_issues(unlinked_run.run_id,[issue],[resolving])

def test_background_dependency_revision_keeps_required_explicit_review(store):
    from arc.schemas import ClaimEvidenceReview
    from arc.validation import ProtocolViolation,validate_revision
    ev=evidence(store,source(store))
    payload=card_payload()
    payload["claims"]=[{"claim_id":"new_hypothesis","version":1,"text":"A bounded hypothesis.","conditions":["condition A"],"kind":"hypothesis","evidence_ids":[ev.evidence_id]}]
    card=store.save_card(payload)
    changed=card.draft.model_copy(deep=True)
    changed.claims[0].version=2
    changed.claims[0].conditions=["condition B"]
    # The existing developer boundary must still reject an undeclared changed
    # dependency before any revision is accepted.
    class Revision:
        unchanged_problem_anchor=card.draft.problem_anchor
        proposed_revision=changed
        affected_claims=[]
        evidence_review=[]
    with pytest.raises(ProtocolViolation,match="AFFECTED_CLAIMS_COVERAGE"):
        validate_revision(store,card,Revision())
    Revision.affected_claims=["new_hypothesis"]
    with pytest.raises(ProtocolViolation,match="CLAIM_REVIEW_COVERAGE"):
        validate_revision(store,card,Revision())
    Revision.evidence_review=[ClaimEvidenceReview(claim_id="new_hypothesis",claim_version=2,
        evidence_ids=[ev.evidence_id],still_applicable=False,explanation="The changed condition was checked.")]
    with pytest.raises(ProtocolViolation,match="REVISED_CLAIM_INHERITS_INVALID_EVIDENCE"):
        validate_revision(store,card,Revision())
    Revision.evidence_review[0].still_applicable=True
    validate_revision(store,card,Revision())
    assert store.claim_evidence_bindings(changed)[0]["verification_transferred"] is False
