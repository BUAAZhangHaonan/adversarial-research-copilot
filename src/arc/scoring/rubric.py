from __future__ import annotations

import re
from dataclasses import dataclass

from arc.schemas import DebateConfig, RoundRecord, ScoreCard


_SCORE_PATTERNS = {
    "novelty": re.compile(r"novelty\D+([1-5])", re.IGNORECASE),
    "feasibility": re.compile(r"feasibility\D+([1-5])", re.IGNORECASE),
    "falsifiability": re.compile(r"falsifiability\D+([1-5])", re.IGNORECASE),
    "evaluation_clarity": re.compile(r"evaluation[_\s-]*clarity\D+([1-5])", re.IGNORECASE),
    "resource_fit": re.compile(r"resource[_\s-]*fit\D+([1-5])", re.IGNORECASE),
}


@dataclass
class ConvergenceStatus:
    should_stop: bool
    reason: str


def parse_scorecard(moderator_text: str) -> ScoreCard:
    values: dict[str, int] = {}
    for key, pattern in _SCORE_PATTERNS.items():
        match = pattern.search(moderator_text)
        if not match:
            values[key] = 3
            continue
        values[key] = int(match.group(1))
    return ScoreCard(**values)


def parse_decision(moderator_text: str) -> str:
    text = moderator_text.upper()
    if re.search(r"\bSTOP\b", text):
        return "STOP"
    return "CONTINUE"


def parse_bullets(section_text: str) -> list[str]:
    lines = [ln.strip() for ln in section_text.splitlines()]
    items = []
    for ln in lines:
        if ln.startswith("-") or ln.startswith("*"):
            items.append(ln.lstrip("-* ").strip())
    return [x for x in items if x]


def extract_section(text: str, section_name: str) -> str:
    pattern = re.compile(rf"{re.escape(section_name)}\s*\n(.*?)(\n#|\n\d+\.|\Z)", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def assess_convergence(rounds: list[RoundRecord], config: DebateConfig) -> ConvergenceStatus:
    if not rounds:
        return ConvergenceStatus(False, "no rounds")

    latest = rounds[-1]
    if latest.decision == "STOP" and len(rounds) >= config.min_rounds_before_stop:
        return ConvergenceStatus(True, "moderator stop")

    if len(rounds) < config.required_stable_rounds:
        return ConvergenceStatus(False, "insufficient stable rounds")

    recent = rounds[-config.required_stable_rounds :]
    no_new_blockers = all(len(r.unresolved_blockers) == 0 for r in recent)
    score_ok = all(r.scorecard.average >= config.score_threshold for r in recent)

    if no_new_blockers and score_ok and len(rounds) >= config.min_rounds_before_stop:
        return ConvergenceStatus(True, "score and blockers converged")

    return ConvergenceStatus(False, "continue improving")
