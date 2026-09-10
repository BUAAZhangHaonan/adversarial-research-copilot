"""Lightweight pre-research outputs. No provider or scientific scoring logic."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiscoveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceNote(DiscoveryModel):
    source_id: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    relevance: str = Field(min_length=1)
    access: Literal["metadata", "abstract", "passage", "full_text", "code", "secondary"]
    limits: str = ""


class FieldBrief(DiscoveryModel):
    overview: str = Field(min_length=1)
    research_lines: list[str]
    openings: list[str]
    source_notes: list[SourceNote]
    search_limits: list[str]


class IdeaSeed(DiscoveryModel):
    title: str = Field(min_length=1)
    question: str = Field(min_length=1)
    insight: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    difference_from_known: str = Field(min_length=1)
    source_ids: list[str]
    key_unknown: str = Field(min_length=1)


class SketchResult(DiscoveryModel):
    action: Literal["submit", "skip", "stop"]
    seed: IdeaSeed | None
    reason: str = Field(min_length=1)
    next_search: str | None = None

    @model_validator(mode="after")
    def check_submission_shape(self):
        if (self.action == "submit") != (self.seed is not None):
            raise ValueError("submit_requires_seed_other_actions_require_null")
        return self


class CandidateRelation(DiscoveryModel):
    kind: Literal["independent", "alternative_route", "evaluation_support", "overlap", "not_compared"]
    related_draw_ids: list[str]
    explanation: str = Field(min_length=1)


class TriageResult(DiscoveryModel):
    action: Literal["investigate", "park", "drop"]
    reason: str = Field(min_length=1)
    strongest_objection: str = Field(min_length=1)
    check_questions: list[str]
    candidate_relation: CandidateRelation | None = None

    @model_validator(mode="after")
    def check_dispatch_shape(self):
        if self.action == "investigate" and not any(q.strip() for q in self.check_questions):
            raise ValueError("investigate_requires_question")
        return self


class NearestWork(DiscoveryModel):
    source_id: str = Field(min_length=1)
    already_established: str = Field(min_length=1)
    remaining_difference: str = Field(min_length=1)
    uncertainty: str = ""


class ResourceHint(DiscoveryModel):
    gpu_type: str | None = None
    gpu_count: int | None = Field(default=None, ge=0)
    training_hours_estimate: str | None = None
    inference_hours_estimate: str | None = None
    basis: str = Field(min_length=1)


class CurrentUnderstanding(DiscoveryModel):
    core_insight: str = Field(min_length=1)
    invalidated_premises: list[str]
    decisive_unknown: str = Field(min_length=1)
    why_existing_insufficient: str = Field(min_length=1)


class FieldRevision(DiscoveryModel):
    overview: str | None = Field(default=None, min_length=1)
    research_lines: list[str] | None = None
    openings: list[str] | None = None


class IdeaNote(DiscoveryModel):
    seed: IdeaSeed
    decision: Literal["discuss", "lead", "drop"]
    reason: str = Field(min_length=1)
    nearest_work: list[NearestWork]
    feasibility: str = Field(min_length=1)
    resources: ResourceHint
    main_risk: str = Field(min_length=1)
    next_question: str = Field(min_length=1)
    source_notes: list[SourceNote]
    limits: list[str]
    changes_from_seed: list[str]
    current_understanding: CurrentUnderstanding | None = None


class CandidateCheck(DiscoveryModel):
    note: IdeaNote
    field_updates: list[SourceNote] = Field(default_factory=list)
    field_revision: FieldRevision | None = None


DISCOVERY_RESULT_SCHEMAS = {
    "scout.SURVEY": FieldBrief,
    "ideator.SKETCH": SketchResult,
    "editor.TRIAGE": TriageResult,
    "scout.CHECK": CandidateCheck,
}
