"""The versioned input for a user-selected external research idea."""
from __future__ import annotations

import hashlib
import json
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from .discovery_models import IdeaSeed, FieldBrief, SourceNote
from .schemas import SourceRecord, SourceType

Access = Literal["metadata", "abstract", "passage", "full_text", "code", "secondary"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Origin(Input):
    system: Literal["ScholarRadar"]
    direction_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)


class StageRequest(Input):
    stage: Literal["develop", "run"]
    focus: str = Field(min_length=1)
    boundaries: list[str] = Field(default_factory=list)


class Proposal(Input):
    title: str = Field(min_length=1)
    question: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    expected_value: str = Field(min_length=1)
    claimed_difference: str = Field(min_length=1)
    decisive_unknown: str = Field(min_length=1)

    def seed(self, ids: list[str]) -> IdeaSeed:
        return IdeaSeed(title=self.title, question=self.question, insight=self.hypothesis,
                        why_it_matters=self.expected_value, difference_from_known=self.claimed_difference,
                        key_unknown=self.decisive_unknown, source_ids=ids)


def fingerprint(value) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


class ExternalSource(Input):
    external_source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str
    version: str | None = None
    work_id: str | None = None
    revision_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    access: Access
    content: str | None = None
    start_char: int = Field(0, ge=0)
    total_chars: int | None = Field(None, ge=0)
    source_type: SourceType = "paper"

    @field_validator("url")
    @classmethod
    def public_location(cls, value):
        link = urlsplit(value)
        if link.scheme not in {"http", "https"} or not link.hostname or link.username or link.password:
            raise ValueError("expected an original HTTP(S) source location")
        return value

    @model_validator(mode="after")
    def check_extent(self):
        if self.access == "metadata" and self.content:
            raise ValueError("metadata has no source body")
        if self.access != "metadata" and not (self.content and self.content.strip()):
            raise ValueError("this reading level requires the corresponding text")
        end = self.start_char + len(self.content or "")
        if self.total_chars is not None and end > self.total_chars:
            raise ValueError("text exceeds its declared extent")
        if self.access == "full_text" and (self.start_char or self.total_chars != end):
            raise ValueError("full text requires the complete declared extent")
        return self

    def register(self, store):
        representation = "external:" + fingerprint([
            self.external_source_id, self.work_id, self.revision_id, self.url, self.version,
            self.access, self.start_char, len(self.content or ""),
        ])
        origin = "metadata" if self.access == "metadata" else (
            "secondary_analysis" if self.access == "secondary" else "original")
        record = SourceRecord(source_id="src_"+fingerprint(representation)[:32],
            representation_id=representation, title=self.title, url=self.url, version=self.version,
            source_type=self.source_type, content_origin=origin,
            access_status="retrieved" if self.content else "metadata_only",
            content_complete=self.access == "full_text",
            content_start_char=self.start_char, content_total_chars=self.total_chars)
        return store.register_source(record, content=self.content).source_id


class ExternalNote(Input):
    external_source_id: str
    finding: str = Field(min_length=1)
    relevance: str = Field(min_length=1)
    access: Access
    limits: str = ""


class SelectedIdea(Input):
    schema_version: Literal["radar.arc.selected-idea.v1"]
    handoff_id: str = Field(min_length=1, max_length=200)
    idea_id: str | None = None
    origin: Origin
    request: StageRequest
    proposal: Proposal
    sources: list[ExternalSource]
    source_notes: list[ExternalNote]
    assets: list[JsonValue] = Field(default_factory=list)
    resource_conditions: dict[str, JsonValue] = Field(default_factory=dict)
    profile: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_links(self):
        entries = {s.external_source_id: s for s in self.sources}
        if len(entries) != len(self.sources):
            raise ValueError("duplicate external source")
        for note in self.source_notes:
            source = entries.get(note.external_source_id)
            if source is None:
                raise ValueError("source note references an unknown input source")
            if note.access != source.access and not (
                note.access == "metadata" or source.access == "full_text" and note.access == "passage"
            ):
                raise ValueError("note access exceeds its source representation")
        return self

    def register_materials(self, store):
        from .discovery_validation import validate_source_access

        mapping = []
        for source in self.sources:
            sid = source.register(store)
            mapping.append({**source.model_dump(exclude={"content"}), "source_id": sid})
        ids = {s["external_source_id"]: s["source_id"] for s in mapping}
        notes = [SourceNote(source_id=ids[n.external_source_id],
                            **n.model_dump(exclude={"external_source_id"})) for n in self.source_notes]
        brief = FieldBrief(overview=self.proposal.question, research_lines=[], openings=[],
                           source_notes=notes, search_limits=list(self.request.boundaries))
        validate_source_access(store, brief)
        return self.proposal.seed(list(dict.fromkeys(ids.values()))), brief, mapping
