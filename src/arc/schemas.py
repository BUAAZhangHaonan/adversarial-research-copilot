"""Typed research contracts; model judgments do not control accounting."""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Annotated, Generic, Literal, TypeVar
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

def utc_now() -> str:
    return datetime.now(UTC).isoformat()

def stable_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

Assessment = Literal["PROMISING", "NEEDS_EVIDENCE", "REJECTED", "SCOPE_CHANGE_PROPOSED"]
NextAction = Literal["REASON", "RETRIEVE", "HANDOFF_EXPERIMENT", "STOP", "PROPOSE_SCOPE_CHANGE"]
RunStatus = Literal["RUNNING", "COMPLETED", "PAUSED_BUDGET", "PAUSED_EXTERNAL", "PAUSED_PROTOCOL", "PAUSED_SCOPE_CHANGE", "ERROR", "CANCELLED"]
Selection = Literal["MAIN_REPORT", "LEAD_ONLY", "NOT_RETAINED"]
IssueStatus = Literal["open", "needs_retrieval", "needs_experiment", "resolved", "withdrawn"]
ContributionType = Literal["new_problem", "new_method", "new_mechanism", "new_boundary"]
EvidenceRelation = Literal["supports", "challenges", "limits", "motivates", "unresolved"]
SourceType = Literal["paper", "author_code", "official_documentation", "author_blog", "community", "review", "news", "secondary_analysis", "user_material", "web_unclassified"]
LocatorStatus = Literal["verified", "locator_unverified", "source_unavailable"]

class Subject(StrictModel):
    campaign_id: str | None
    run_id: str | None
    card_id: str | None
    card_version: int | None = Field(ge=1)

    @model_validator(mode="after")
    def paired_card(self):
        if (self.card_id is None) != (self.card_version is None):
            raise ValueError("card_id_and_version_must_be_paired")
        return self

class EvidenceRequest(StrictModel):
    request_local_id: str = Field(min_length=1)
    claim_id: str | None
    issue_id: str | None
    draw_id: str | None
    question: str = Field(min_length=1)
    target_source_ids: list[str]
    queries: list[str]
    purpose: str = Field(min_length=1)
    decision_if_supported: str = Field(min_length=1)
    decision_if_contradicted: str = Field(min_length=1)

    @model_validator(mode="after")
    def actionable(self):
        if not (self.target_source_ids or self.queries):
            raise ValueError("evidence_request_requires_target")
        return self

class CapabilityRequest(StrictModel):
    blocked_question: str = Field(min_length=1)
    needed_operation: str = Field(min_length=1)
    input_fields: list[str]
    required_output: str = Field(min_length=1)
    provenance_needs: str
    cost_visibility_needs: str
    acceptance_example: str
    current_limitation: str = Field(min_length=1)
    proposed_change: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    alternatives: list[str] = Field(min_length=1)
    expected_impact: str = Field(min_length=1)

class CapabilityReview(StrictModel):
    assessment: Literal["recommended", "needs_information", "not_recommended"]
    rationale: str = Field(min_length=1)
    recommended_option: str | None
    implementation_scope: list[str]
    validation_plan: list[str]

    @model_validator(mode="after")
    def actionable_recommendation(self):
        if self.assessment == "recommended" and not (
            self.recommended_option and self.recommended_option.strip()
            and self.implementation_scope and all(x.strip() for x in self.implementation_scope)
            and self.validation_plan and all(x.strip() for x in self.validation_plan)
        ):
            raise ValueError("recommended_capability_requires_scope_and_validation")
        return self

T = TypeVar("T", bound=BaseModel)

class Envelope(StrictModel, Generic[T]):
    schema_version: Literal["arc.v1"]
    task_id: str = Field(min_length=1)
    subject: Subject
    result_status: Literal["complete", "needs_evidence", "blocked"]
    result: T | None
    evidence_requests: list[EvidenceRequest]
    capability_requests: list[CapabilityRequest]
    note: str | None

    @model_validator(mode="after")
    def completion_contract(self):
        if self.result_status == "complete" and self.result is None:
            raise ValueError("complete_requires_result")
        if self.result_status != "complete" and not self.note:
            raise ValueError("incomplete_requires_reason")
        if self.result_status == "needs_evidence" and not self.evidence_requests:
            raise ValueError("needs_evidence_requires_request")
        for request in self.evidence_requests:
            if not (request.claim_id or request.issue_id or request.draw_id):
                # Before a card/draw exists, the request belongs to this actual
                # task and run; direct proposal imports need no campaign.
                if not (self.subject.card_id is None and self.subject.run_id):
                    raise ValueError("evidence_request_requires_subject")
        ids = [r.request_local_id for r in self.evidence_requests]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_request_local_id")
        return self

class ProblemAnchor(StrictModel):
    question: str = Field(min_length=1)
    research_object: str = Field(min_length=1)
    conditions: list[str]
    anti_scope: list[str]

class Contribution(StrictModel):
    primary_type: ContributionType
    secondary_types: list[ContributionType]
    knowledge_increment: str = Field(min_length=1)
    decision_changed: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_types(self):
        if self.primary_type in self.secondary_types or len(self.secondary_types) != len(set(self.secondary_types)):
            raise ValueError("duplicate_contribution_type")
        return self

class Motivation(StrictModel):
    observation_or_deficit: str = Field(min_length=1)
    evidence_ids: list[str]
    unresolved_assumptions: list[str]

class ClosestWorkDelta(StrictModel):
    source_ids: list[str]
    established_claim: str
    remaining_claim: str
    search_limits: list[str]

class Hypotheses(StrictModel):
    main_or_competing_explanations: list[str] = Field(min_length=1)
    distinct_predictions: list[str] = Field(min_length=1)
    favored_only_if_justified: str | None

class NecessaryComponent(StrictModel):
    component: str
    necessity: str

class MethodPlan(StrictModel):
    simplest_path: str
    necessary_components: list[NecessaryComponent]
    stitching_assessment: str

class OutcomeInterpretation(StrictModel):
    outcome: str
    interpretation: str
    validity_limit: str

class MinimalTest(StrictModel):
    intervention: str
    controls: list[str]
    measurements: list[str]
    positive_controls: list[str]
    outcome_interpretations: list[OutcomeInterpretation] = Field(min_length=1)
    confounds_not_yet_ruled_out: list[str]

class NumericRange(StrictModel):
    lower: float = Field(ge=0, allow_inf_nan=False)
    upper: float = Field(ge=0, allow_inf_nan=False)
    unit: Literal["GPU-hours", "hours"]

    @model_validator(mode="after")
    def ordered(self):
        if self.upper < self.lower:
            raise ValueError("range_upper_below_lower")
        return self

class WorkloadAssumptions(StrictModel):
    model_size: str | None
    precision: str | None
    sequence_length: int | None = Field(ge=1)
    data_amount: str | None
    steps: int | None = Field(ge=0)
    parallelism: str | None
    non_gpu_steps: str | None

class ResourceEstimate(StrictModel):
    model_config = ConfigDict(json_schema_extra={"allOf": [
        {"properties": {
            "wall_hours_range": {"properties": {"unit": {"const": "hours"}}},
            "training_gpu_hours_range": {"properties": {"unit": {"const": "GPU-hours"}}},
            "inference_gpu_hours_range": {"properties": {"unit": {"const": "GPU-hours"}}},
        }},
        {"if": {"properties": {"gpu_count": {"exclusiveMinimum": 0}}},
         "then": {"properties": {
             "gpu_type": {"type": "string", "minLength": 1},
             "gpu_memory_gb_assumption": {"type": "number", "exclusiveMinimum": 0},
         }}},
        {"if": {"properties": {"gpu_count": {"const": 0}}},
         "then": {"properties": {
             "training_gpu_hours_range": {"properties": {"upper": {"maximum": 0}}},
             "inference_gpu_hours_range": {"properties": {"upper": {"maximum": 0}}},
         }}},
    ]})
    gpu_type: str | None
    gpu_memory_gb_assumption: float | None = Field(ge=0, allow_inf_nan=False)
    gpu_count: int = Field(ge=0, strict=True)
    training_gpu_hours_range: NumericRange | None
    inference_gpu_hours_range: NumericRange | None
    wall_hours_range: NumericRange
    workload_assumptions: WorkloadAssumptions
    estimate_basis: str
    uncertainty: str

    @model_validator(mode="after")
    def units(self):
        if self.wall_hours_range.unit != "hours":
            raise ValueError("wall_time_unit")
        for interval in (self.training_gpu_hours_range, self.inference_gpu_hours_range):
            if interval is not None and interval.unit != "GPU-hours":
                raise ValueError("gpu_time_unit")
        if self.gpu_count > 0 and (not self.gpu_type or not self.gpu_memory_gb_assumption):
            raise ValueError("gpu_configuration_required")
        if self.gpu_count==0 and any(interval is not None and interval.upper>0 for interval in (self.training_gpu_hours_range,self.inference_gpu_hours_range)):
            raise ValueError("positive_gpu_hours_require_gpu")
        return self

class CardRisks(StrictModel):
    decisive_risks: list[str]
    missing_prerequisites: list[str]
    reopen_conditions: list[str]

class Claim(StrictModel):
    claim_id: str
    version: int = Field(ge=1, strict=True)
    text: str
    conditions: list[str]
    kind: Literal["empirical", "logical", "definition", "hypothesis"]
    evidence_ids: list[str]

class CardDraft(StrictModel):
    title: str = Field(min_length=1)
    problem_anchor: ProblemAnchor
    contribution: Contribution
    motivation: Motivation
    closest_work_delta: ClosestWorkDelta
    hypotheses: Hypotheses
    method: MethodPlan
    minimal_test: MinimalTest
    resources: ResourceEstimate
    risks: CardRisks
    claims: list[Claim]

    @model_validator(mode="after")
    def unique_claims(self):
        ids = [c.claim_id for c in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_claim_id")
        return self

class ResearchCard(StrictModel):
    card_id: str
    version: int = Field(ge=1, strict=True)
    draft: CardDraft
    selection: Selection | None = None
    assessment: Assessment | None = None
    selection_result: SelectorResult | ScientificReview | None = None
    parent_version: int | None = Field(default=None, ge=1)
    created_at: str = Field(default_factory=utc_now)

class SourceRecord(StrictModel):
    source_id: str = Field(default_factory=lambda: stable_id("src"))
    title: str
    url: str | None
    doi: str | None = None
    arxiv_id: str | None = None
    version: str | None = None
    source_type: SourceType
    access_status: Literal["retrieved", "metadata_only", "source_unavailable"]
    content_origin: Literal["original", "secondary_analysis", "metadata"]
    canonical_id: str | None = None
    origin_source_id: str | None = None
    content_path: str | None = None
    content_sha256: str | None = None
    content_complete: bool = True
    content_total_chars: int | None = Field(default=None, ge=0)
    representation_id: str | None = None
    retrieved_at: str = Field(default_factory=utc_now)

class EvidenceRecord(StrictModel):
    evidence_id: str = Field(default_factory=lambda: stable_id("ev"))
    source_id: str
    claim_id: str
    claim_version: int = Field(ge=1, strict=True)
    target_claim_fingerprint: str | None = None
    claim: str
    conditions: list[str]
    locator: str | None
    excerpt: str | None
    relation: EvidenceRelation
    origin: Literal["original", "secondary_analysis", "author_interpretation", "inference"]
    locator_status: LocatorStatus
    verification_status: Literal["verified", "unverified", "contradicted"]
    support_explanation: str
    run_id: str | None = None
    created_at: str = Field(default_factory=utc_now)

class Issue(StrictModel):
    issue_id: str
    claim_id: str
    claim_version: int = Field(ge=1, strict=True)
    content: str
    status: IssueStatus
    evidence_ids: list[str]
    resolution_criterion: str
    change_this_round: str
    next_action: NextAction
    claim_kind: Literal["empirical", "logical", "definition", "hypothesis"] = "empirical"
    redirect_to: str | None = None

class IssueTransition(StrictModel):
    issue_id: str
    from_status: IssueStatus | None
    to_status: IssueStatus
    change_this_round: str = Field(min_length=1)
    basis_evidence_ids: list[str]
    basis_argument: str | None
    resolution_reason: str | None
    new_evidence_or_argument: str | None = None

class DirectionChangeDraft(StrictModel):
    proposed_problem_anchor: ProblemAnchor
    trigger_evidence_ids: list[str] = Field(min_length=1)
    original_sources_revisited: list[str] = Field(min_length=1)
    missed_evidence_analysis: str

class DirectionChange(DirectionChangeDraft):
    direction_change_id: str = Field(default_factory=lambda: stable_id("direction"))
    run_id: str
    parent_card_id: str
    parent_card_version: int = Field(ge=1)
    status: Literal["FROZEN", "APPROVED", "DECLINED"] = "FROZEN"
    created_at: str = Field(default_factory=utc_now)

ArchiveRelationType = Literal["same_contribution", "related_but_distinct", "reopening_candidate", "insufficient_record"]

class ArchiveRelation(StrictModel):
    archive_card_id: str
    archive_card_version: int = Field(ge=1)
    relation: ArchiveRelationType
    rationale: str
    reopening_condition_met: bool
    reopening_condition: str | None = None
    new_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reopening_basis(self):
        if self.reopening_condition_met:
            if self.relation!="reopening_candidate" or not self.reopening_condition or not self.new_evidence_ids:
                raise ValueError("reopening_requires_condition_and_new_evidence")
        return self

class Campaign(StrictModel):
    campaign_id: str
    topic: str
    boundaries: list[str]
    max_draws: int = Field(default=5, ge=1, le=5)
    draws_started: int = Field(default=0, ge=0, le=5)
    retained_families: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    budget_account_id: str | None = None
    parent_card_id: str | None = None
    parent_card_version: int | None = None
    created_at: str = Field(default_factory=utc_now)

class RunRecord(StrictModel):
    run_id: str
    mode: Literal["discover", "develop", "run", "evaluation"]
    campaign_id: str | None = None
    card_id: str | None = None
    card_version: int | None = Field(default=None, ge=1)
    budget_account_id: str | None = None
    status: RunStatus = "RUNNING"
    stop_reason: str | None = None
    assessment: Assessment | None = None
    config: dict[str, JsonValue] = Field(default_factory=dict)
    state: dict[str, JsonValue] = Field(default_factory=dict)
    prompt_version: str = ""
    code_version: str = ""
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

TaskStatus = Literal["PENDING", "RESERVED", "IN_FLIGHT", "RESPONSE_SAVED", "ACCEPTED", "PAUSED_PROTOCOL", "PAUSED_EXTERNAL", "UNKNOWN", "ERROR"]

class TaskRecord(StrictModel):
    task_id: str
    run_id: str
    input_hash: str
    prompt_hash: str
    model_config_hash: str
    status: TaskStatus = "PENDING"
    attempt_ids: list[str] = Field(default_factory=list)
    response_artifact_path: str | None = None
    accepted_result: JsonValue = None
    rendered_prompt_path: str | None = None
    environment_snapshot_path: str | None = None
    environment_snapshot_hash: str | None = None
    prompt_manifest: JsonValue = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    model_id: str | None = None
    error: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

class SearchTrace(StrictModel):
    trace_id: str
    operation: str
    query: str
    source_ids: list[str]

class Finding(StrictModel):
    claim: str
    claim_id: str | None = None
    claim_version: int | None = Field(default=None, ge=1)
    conditions: list[str]
    source_id: str
    locator: str | None
    locator_status: LocatorStatus
    relation: EvidenceRelation
    origin: Literal["original", "secondary_analysis", "author_interpretation", "inference"]
    excerpt: str | None
    support_explanation: str

    @model_validator(mode="after")
    def target_claim_is_paired(self):
        if (self.claim_id is None)!=(self.claim_version is None):
            raise ValueError("finding_target_claim_requires_id_and_version")
        return self

class InvestigatorResult(StrictModel):
    questions_addressed: list[str]
    actual_searches: list[SearchTrace]
    findings: list[Finding]
    contrary_findings: list[Finding]
    source_access_limits: list[str]
    implications_for_current_card: list[str]
    unresolved_questions: list[str]
    recommended_next_action: NextAction

class LibrarianResult(StrictModel):
    comparisons: list[ArchiveRelation]
    records_opened: list[str]
    retrieval_scope: str
    unsearched_limits: list[str]
    needs_additional_lookup: bool

class Mandate(StrictModel):
    topic: str
    research_object: str
    scope_in: list[str]
    scope_out: list[str]
    known_constraints: list[str]
    unknown_constraints: list[str]

class FrameResult(StrictModel):
    mandate: Mandate
    initial_search_questions: list[str]

class NextDrawResult(StrictModel):
    continue_or_stop: Literal["CONTINUE", "STOP"]
    proposed_family: str | None
    anchor_evidence_ids: list[str]
    distinct_from_retained: str | None
    relevant_archive_relations: list[ArchiveRelation]
    missing_information: list[str]
    why_this_draw_is_worthwhile: str | None

    @model_validator(mode="after")
    def continuing(self):
        if self.continue_or_stop == "CONTINUE" and not (self.proposed_family and self.why_this_draw_is_worthwhile):
            raise ValueError("continue_requires_family_and_reason")
        return self

class ComposeResult(StrictModel):
    card_candidate: CardDraft | None
    composition_reason: str
    unresolved_prerequisites: list[str]

class ClosestWork(StrictModel):
    source_id: str
    evidence_ids: list[str]
    established_claim: str
    conditions: list[str]
    card_claim: str
    coverage: Literal["covered", "partial", "not_covered", "unknown"]
    rationale: str

class NoveltyResult(StrictModel):
    closest_works: list[ClosestWork]
    contribution_coverage: Literal["covered", "partial", "not_covered", "unknown"]
    defensible_delta: str
    search_scope: str
    unchecked_items: list[str]
    recommended_selection_effect: str

class SelectionCheck(StrictModel):
    status: Literal["supported", "refuted", "unknown", "not_applicable"]
    evidence_ids: list[str]
    rationale: str

class SelectionChecks(StrictModel):
    motivation: SelectionCheck
    knowledge_delta: SelectionCheck
    test_identifiability: SelectionCheck
    resource_path: SelectionCheck
    stitching: SelectionCheck

class SelectorResult(StrictModel):
    selection: Selection
    assessment: Literal["PROMISING", "NEEDS_EVIDENCE", "REJECTED"]
    contribution_summary: str
    why_worth_investigating: str
    closest_work_delta: str
    hypothesis_plausibility: str
    test_identifiability: str
    stitching_check: str
    resource_assessment: str
    unverified_assumptions: list[str]
    decisive_risks: list[str]
    evidence_ids: list[str]
    next_action: NextAction
    reopening_condition: str | None
    selection_checks: SelectionChecks
    stitching_type: Literal["routine_components", "unsupported_stitching", "combination_exception", "not_applicable"]
    meaningful_gain_basis: str | None
    interaction_prediction: str | None
    matched_budget_test: str | None

    @model_validator(mode="after")
    def selection_consistency(self):
        if self.selection == "MAIN_REPORT" and self.assessment != "PROMISING":
            raise ValueError("main_report_requires_promising")
        if self.selection == "LEAD_ONLY" and self.assessment != "NEEDS_EVIDENCE":
            raise ValueError("lead_requires_needs_evidence")
        if self.selection == "NOT_RETAINED" and not self.reopening_condition:
            raise ValueError("not_retained_requires_reopening_condition")
        return self

class ClaimEvidenceReview(StrictModel):
    claim_id: str
    claim_version: int = Field(ge=1)
    evidence_ids: list[str]
    still_applicable: bool
    explanation: str

class DeveloperResult(StrictModel):
    proposed_revision: CardDraft | None
    direction_change: DirectionChangeDraft | None
    unchanged_problem_anchor: ProblemAnchor
    change_summary: list[str]
    affected_claims: list[str]
    evidence_review: list[ClaimEvidenceReview]
    minimal_test: MinimalTest | None
    resources: ResourceEstimate | None
    remaining_issues: list[str]
    next_action: NextAction

    @model_validator(mode="after")
    def one_path(self):
        if (self.proposed_revision is None) == (self.direction_change is None):
            raise ValueError("revision_xor_direction_change")
        if self.direction_change is not None and self.next_action != "PROPOSE_SCOPE_CHANGE":
            raise ValueError("scope_change_action_required")
        return self

class IssueResponse(StrictModel):
    issue_id: str
    response: str
    evidence_ids: list[str]
    proposed_change: str

class ProposerResult(StrictModel):
    claims_defended: list[str]
    claims_narrowed: list[str]
    claims_withdrawn: list[str]
    proposed_method_changes: list[str]
    issue_responses: list[IssueResponse]
    new_argument_or_evidence: list[str]
    suggested_next_action: NextAction

class Criticism(StrictModel):
    issue_id: str | None
    local_label: str | None
    severity: Literal["decisive", "material", "minor"]
    claim_id: str
    claim: str
    rationale: str
    impact: str
    evidence_ids: list[str]
    resolution_criterion: str

    @model_validator(mode="after")
    def identity(self):
        if (self.issue_id is None) == (self.local_label is None):
            raise ValueError("criticism_identity_xor")
        return self

class SkepticResult(StrictModel):
    criticisms: list[Criticism]
    resolved_objections: list[str]
    surviving_decisive_issues: list[str]
    required_evidence_or_test: list[str]
    suggested_next_action: NextAction

class ModeratorResult(StrictModel):
    assessment: Assessment
    next_action: NextAction
    stop_reason: str | None
    concise_ruling: str
    issue_transitions: list[IssueTransition]
    updated_issues: list[Issue]
    decisive_evidence_ids: list[str]
    proposed_card_revision: CardDraft | None
    external_test_requirements: list[str]
    direction_change: DirectionChangeDraft | None

    @model_validator(mode="after")
    def consistent_action(self):
        ids = [i.issue_id for i in self.updated_issues]
        tids = [t.issue_id for t in self.issue_transitions]
        if len(ids) != len(set(ids)) or len(tids) != len(set(tids)):
            raise ValueError("duplicate_issue_id")
        if set(ids) != set(tids):
            raise ValueError("issue_transition_coverage")
        if self.next_action == "HANDOFF_EXPERIMENT" and not self.external_test_requirements:
            raise ValueError("handoff_requires_test")
        if self.next_action=="REASON" and not any(i.status=="open" and i.next_action=="REASON" for i in self.updated_issues):
            raise ValueError("reason_requires_actionable_open_issue")
        if self.next_action=="RETRIEVE" and not any(i.status=="needs_retrieval" and i.next_action=="RETRIEVE" for i in self.updated_issues):
            raise ValueError("retrieve_requires_bound_issue")
        if self.next_action == "PROPOSE_SCOPE_CHANGE" and (self.direction_change is None or self.assessment != "SCOPE_CHANGE_PROPOSED"):
            raise ValueError("scope_change_requires_evidence_event")
        if self.next_action != "PROPOSE_SCOPE_CHANGE" and self.direction_change is not None:
            raise ValueError("unrequested_direction_change")
        return self

class ReportCardSections(StrictModel):
    card_id: str
    card_version: int = Field(ge=1)
    conclusion: str
    why_worth_investigating: str
    closest_work_delta: str
    hypothesis_and_alternatives: str
    minimal_test: str
    resources: str
    decisive_risk: str
    next_action: str
    citation_ids: list[str]

class ReporterResult(StrictModel):
    overview: str
    cards: list[ReportCardSections]
    card_order: list[str]
    scope_and_limits: str
    citation_ids: list[str]

class ConceptionResult(StrictModel):
    card_candidate: CardDraft | None
    continue_or_stop: Literal['CONTINUE', 'STOP']
    composition_reason: str = Field(min_length=1)
    distinct_from_retained: str

    @model_validator(mode='after')
    def stopped_card(self):
        if self.continue_or_stop == 'STOP' and self.card_candidate is not None:
            raise ValueError('STOP_requires_card_candidate_null; use_CONTINUE_to_submit_candidate')
        return self

class ScientificFinding(StrictModel):
    finding_id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    quoted_text: str
    reason: str = Field(min_length=1)
    consequence: str = Field(min_length=1)
    evidence_ids: list[str]
    source_ids: list[str]
    severity: Literal['repairable', 'fatal', 'missing_evidence']
    required_change: str = Field(min_length=1)
    acceptance_test: str = Field(min_length=1)

class VerificationWork(StrictModel):
    question: str = Field(min_length=1)
    method: Literal['source_read', 'counterexample', 'derivation', 'comparison']
    answer: str = Field(min_length=1)
    evidence_ids: list[str]
    source_ids: list[str]

class FindingResolution(StrictModel):
    finding_id: str
    status: Literal['resolved', 'unresolved', 'reviewer_error']
    reason: str = Field(min_length=1)

class ClaimEditAssessment(StrictModel):
    claim_id: str
    change_kind: Literal['unchanged_meaning', 'substantive']
    reason: str = Field(min_length=1)

class ScientificReview(StrictModel):
    original_question: str = Field(min_length=1)
    scope_faithful: bool
    core_insight: str = Field(min_length=1)
    value_judgment: Literal['substantial', 'routine', 'unsupported']
    value_reason: str = Field(min_length=1)
    verification_work: list[VerificationWork] = Field(min_length=1)
    decisive_findings: list[ScientificFinding]
    prior_findings: list[FindingResolution]
    edit_assessments: list[ClaimEditAssessment]
    remaining_uncertainty: list[str]
    action: Literal['retain', 'revise', 'needs_evidence', 'reject']

    @model_validator(mode='after')
    def concrete_action(self):
        for items in (self.decisive_findings, self.prior_findings):
            ids = [item.finding_id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError('duplicate_scientific_finding')
        if len({x.claim_id for x in self.edit_assessments}) != len(self.edit_assessments):
            raise ValueError('duplicate_edit_assessment')
        if self.action == 'retain' and (not self.scope_faithful or self.value_judgment != 'substantial'
                or self.decisive_findings or any(x.status == 'unresolved' for x in self.prior_findings)):
            unresolved = [x.finding_id for x in self.prior_findings if x.status == 'unresolved']
            raise ValueError('retention_requires_scope_value_and_no_decisive_error: '
                f'actual scope_faithful={self.scope_faithful}, value_judgment={self.value_judgment}, '
                f'decisive_findings={len(self.decisive_findings)}, unresolved_prior_findings={unresolved}; '
                'required for retain: scope_faithful=true, value_judgment=substantial, '
                'decisive_findings=[], unresolved_prior_findings=[]; '
                'routine value is consistent with reject; correctness is separate from research value.')
        if self.action == 'revise' and not self.decisive_findings:
            raise ValueError('revision_requires_located_scientific_defect')
        return self

    @property
    def selection(self):
        return 'MAIN_REPORT' if self.action == 'retain' else 'NOT_RETAINED' if self.action == 'reject' else 'LEAD_ONLY'

    @property
    def assessment(self):
        return 'PROMISING' if self.action == 'retain' else 'REJECTED' if self.action == 'reject' else 'NEEDS_EVIDENCE'

class TitleSectionUpdate(StrictModel):
    field: Literal['title']
    value: str = Field(min_length=1)

class ProblemAnchorSectionUpdate(StrictModel):
    field: Literal['problem_anchor']
    value: ProblemAnchor

class ContributionSectionUpdate(StrictModel):
    field: Literal['contribution']
    value: Contribution

class MotivationSectionUpdate(StrictModel):
    field: Literal['motivation']
    value: Motivation

class ClosestWorkSectionUpdate(StrictModel):
    field: Literal['closest_work_delta']
    value: ClosestWorkDelta

class HypothesesSectionUpdate(StrictModel):
    field: Literal['hypotheses']
    value: Hypotheses

class MethodSectionUpdate(StrictModel):
    field: Literal['method']
    value: MethodPlan

class MinimalTestSectionUpdate(StrictModel):
    field: Literal['minimal_test']
    value: MinimalTest

class ResourceSectionUpdate(StrictModel):
    field: Literal['resources']
    value: ResourceEstimate

class RiskSectionUpdate(StrictModel):
    field: Literal['risks']
    value: CardRisks

SectionUpdate = Annotated[
    TitleSectionUpdate |
    ProblemAnchorSectionUpdate |
    ContributionSectionUpdate |
    MotivationSectionUpdate |
    ClosestWorkSectionUpdate |
    HypothesesSectionUpdate |
    MethodSectionUpdate |
    MinimalTestSectionUpdate |
    ResourceSectionUpdate |
    RiskSectionUpdate,
    Field(discriminator='field'),
]

class ScientificRevision(StrictModel):
    section_updates: list[SectionUpdate]
    claim_updates: list[Claim]
    remove_claim_ids: list[str]
    addressed_findings: list[FindingResolution]
    change_summary: list[str]
    abandon: bool

    @model_validator(mode='after')
    def unique_changes(self):
        fields = [x.field for x in self.section_updates]
        claims = [x.claim_id for x in self.claim_updates]
        if len(fields) != len(set(fields)) or len(claims) != len(set(claims)):
            raise ValueError('duplicate_scientific_patch_target')
        if len(self.remove_claim_ids) != len(set(self.remove_claim_ids)) or set(claims) & set(self.remove_claim_ids):
            raise ValueError('ambiguous_scientific_claim_patch')
        return self

class CandidateFinding(StrictModel):
    candidate_id: str
    findings: list[str]
    evidence_ids: list[str]

class EvaluatorResult(StrictModel):
    per_candidate_findings: list[CandidateFinding]
    decisive_errors: list[str]
    supported_strengths: list[str]
    unresolved_verifications: list[str]
    preference_if_requested: str | None
    uncertainty: str

RESULT_SCHEMAS: dict[str, type[StrictModel]] = {
    "investigator": InvestigatorResult, "librarian": LibrarianResult,
    "discovery.FRAME": FrameResult, "discovery.NEXT_DRAW": NextDrawResult,
    "discovery.COMPOSE": ComposeResult, "novelty_examiner": NoveltyResult,
    "discovery.CONCEIVE": ConceptionResult, "discovery.REVISE": ScientificRevision,
    "scientific_reviewer": ScientificReview,
    "selector": SelectorResult, "developer": DeveloperResult, "proposer": ProposerResult,
    "skeptic": SkepticResult, "moderator": ModeratorResult, "reporter": ReporterResult,
    "evaluator": EvaluatorResult,
}

ResearchCard.model_rebuild()
