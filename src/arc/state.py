from __future__ import annotations

from pathlib import Path

from arc.prompting import normalize_prompt_language, resolve_prompt_path
from arc.schemas import ResearchState


def load_idea_text(path: str | Path) -> str:
    idea_path = Path(path)
    return idea_path.read_text(encoding="utf-8").strip()


def frame_problem(raw_idea: str) -> str:
    # Keep framing deterministic so convergence behavior is stable in tests.
    language = normalize_prompt_language(None)
    template = resolve_prompt_path("debate", "problem_framer", language).read_text(
        encoding="utf-8")
    return template.replace("{raw_idea}", raw_idea)


def init_state(idea: str) -> ResearchState:
    framed = frame_problem(idea)
    return ResearchState(idea=idea, framed_problem=framed)
