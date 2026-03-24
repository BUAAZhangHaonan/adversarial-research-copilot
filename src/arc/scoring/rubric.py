from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass

import yaml

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
    structured = parse_moderator_payload(moderator_text)
    if structured and isinstance(structured.get("scorecard"), dict):
        raw = structured["scorecard"]
        values = {
            "novelty": int(raw.get("novelty", 3)),
            "feasibility": int(raw.get("feasibility", 3)),
            "falsifiability": int(raw.get("falsifiability", 3)),
            "evaluation_clarity": int(raw.get("evaluation_clarity", 3)),
            "resource_fit": int(raw.get("resource_fit", 3)),
        }
        return ScoreCard(**values)

    values: dict[str, int] = {}
    for key, pattern in _SCORE_PATTERNS.items():
        match = pattern.search(moderator_text)
        if not match:
            values[key] = 3
            continue
        values[key] = int(match.group(1))
    return ScoreCard(**values)


def parse_decision(moderator_text: str) -> str:
    structured = parse_moderator_payload(moderator_text)
    if structured and isinstance(structured.get("continue_or_stop"), str):
        value = structured["continue_or_stop"].strip().upper()
        if value in {"STOP", "CONTINUE"}:
            return value

    text = moderator_text.upper()
    if re.search(r"\bSTOP\b", text):
        return "STOP"
    return "CONTINUE"


def parse_moderator_payload(moderator_text: str) -> dict | None:
    match = re.search(r"```(?:yaml|yml)\s*(.*?)```", moderator_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    payload_text = textwrap.dedent(match.group(1)).strip()

    # Some models emit fenced YAML where the first line has less indent than the rest.
    # Normalize indentation for lines after the first so YAML parser remains stable.
    lines = payload_text.splitlines()
    if len(lines) > 1:
        indents = [len(ln) - len(ln.lstrip()) for ln in lines[1:] if ln.strip()]
        if indents:
            trim = min(indents)
            normalized = [lines[0].lstrip()]
            normalized.extend(ln[trim:] if len(ln) >= trim else ln for ln in lines[1:])
            payload_text = "\n".join(normalized)

    try:
        data = yaml.safe_load(payload_text)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def parse_unresolved_blockers(moderator_text: str) -> list[str]:
    structured = parse_moderator_payload(moderator_text)
    if structured and isinstance(structured.get("unresolved_blockers"), list):
        return [str(x).strip() for x in structured["unresolved_blockers"] if str(x).strip()]
    return parse_bullets(extract_section(moderator_text, "unresolved blockers"))


def parse_required_revisions(moderator_text: str) -> list[str]:
    structured = parse_moderator_payload(moderator_text)
    if structured and isinstance(structured.get("required_revisions"), list):
        return [str(x).strip() for x in structured["required_revisions"] if str(x).strip()]
    return parse_bullets(extract_section(moderator_text, "required revisions"))


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
