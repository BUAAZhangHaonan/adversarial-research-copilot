from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScoreCard(BaseModel):
    novelty: int = Field(ge=1, le=5)
    feasibility: int = Field(ge=1, le=5)
    falsifiability: int = Field(ge=1, le=5)
    evaluation_clarity: int = Field(ge=1, le=5)
    resource_fit: int = Field(ge=1, le=5)

    @property
    def average(self) -> float:
        values = [
            self.novelty,
            self.feasibility,
            self.falsifiability,
            self.evaluation_clarity,
            self.resource_fit,
        ]
        return sum(values) / len(values)


class RoundRecord(BaseModel):
    round_id: int
    round_started_at: datetime | None = None
    proposer_completed_at: datetime | None = None
    skeptic_completed_at: datetime | None = None
    moderator_completed_at: datetime | None = None
    round_completed_at: datetime | None = None
    proposer: str
    skeptic: str
    moderator: str
    scorecard: ScoreCard
    unresolved_blockers: list[str]
    required_revisions: list[str]
    decision: Literal["CONTINUE", "STOP"]
    parse_degraded: bool = False


class DebateConfig(BaseModel):
    max_rounds: int = 6
    min_rounds_before_stop: int = 2
    score_threshold: float = 4.0
    required_stable_rounds: int = 2
    human_checkpoint: bool = False
    require_cross_model_adversary: bool = True
    persist_run_state: bool = True
    stale_resume_hours: int = 24


class ResearchState(BaseModel):
    idea: str
    framed_problem: str
    rounds: list[RoundRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_round(self, record: RoundRecord) -> None:
        self.rounds.append(record)


PipelineStatus = Literal["in_progress", "completed", "failed"]
StageStatus = Literal["not_started", "in_progress", "completed", "failed"]


class PipelineStageRecord(BaseModel):
    name: str
    status: StageStatus = "not_started"
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None


class PipelineState(BaseModel):
    run_id: str
    topic: str
    status: PipelineStatus = "in_progress"
    current_stage: str | None = None
    stages: list[PipelineStageRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @classmethod
    def new(cls, topic: str) -> "PipelineState":
        import uuid

        return cls(run_id=uuid.uuid4().hex, topic=topic)

    def stage(self, name: str) -> PipelineStageRecord:
        for s in self.stages:
            if s.name == name:
                return s
        raise KeyError(name)
