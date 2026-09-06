from __future__ import annotations

import re
from dataclasses import dataclass

from pathlib import Path

from arc.llm_client import LLMClient
from arc.prompting import localized_text, normalize_prompt_language, resolve_prompt_path


@dataclass
class TopicRefineRound:
    round_id: int
    draft: str
    critique: str


def refine_research_topic(
    client: LLMClient,
    writer_model: str,
    reviewer_model: str,
    topic: str,
    rounds: int = 2,
    prompt_language: str = "en",
) -> tuple[str, list[TopicRefineRound]]:
    draft = topic.strip()
    history: list[TopicRefineRound] = []
    language = normalize_prompt_language(prompt_language)

    for rid in range(1, max(1, rounds) + 1):
        critique = history[-1].critique if history else None
        writer_output = client.chat(
            model=writer_model,
            system_prompt=_load_refine_prompt("writer", language),
            user_prompt=_load_refine_prompt("writer_task", language).format(
                topic=draft,
                critique=critique.strip() if critique else localized_text(language, "none", "无"),
            ),
            temperature=0.2,
        )
        refined = extract_refined_topic(writer_output)

        critique_output = client.chat(
            model=reviewer_model,
            system_prompt=_load_refine_prompt("reviewer", language),
            user_prompt=_load_refine_prompt("reviewer_task", language).format(refined=refined),
            temperature=0.2,
        )

        history.append(TopicRefineRound(
            round_id=rid, draft=refined, critique=critique_output.strip()))
        draft = refined

    return draft, history


def extract_refined_topic(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    patterns = [
        r"(?im)^#{1,3}\s*优化题面\s*$",
        r"(?im)^#{1,3}\s*Refined Topic\s*$",
        r"(?im)^优化题面\s*[:：]\s*$",
        r"(?im)^Refined Topic\s*[:：]\s*$",
    ]
    for p in patterns:
        m = re.search(p, cleaned)
        if not m:
            continue
        tail = cleaned[m.end():].strip()
        if not tail:
            continue
        # Stop at next heading if present.
        heading = re.search(r"(?m)^#{1,3}\s+", tail)
        out = tail[: heading.start()].strip() if heading else tail
        first_para = out.split("\n\n", 1)[0].strip()
        if first_para:
            return _single_line(first_para)

    # Fallback: first non-empty line.
    for line in cleaned.splitlines():
        s = line.strip()
        if s:
            return _single_line(s)
    return ""


def build_topic_refine_report(original: str, refined: str, rounds: list[TopicRefineRound]) -> str:
    lines: list[str] = []
    lines.append("# Topic Refinement Report")
    lines.append("")
    lines.append("## Original Topic")
    lines.append(original.strip())
    lines.append("")
    lines.append("## Refined Topic")
    lines.append(refined.strip())
    lines.append("")

    for item in rounds:
        lines.append(f"## Round {item.round_id}")
        lines.append("")
        lines.append("### Draft")
        lines.append(item.draft)
        lines.append("")
        lines.append("### Critique")
        lines.append(item.critique)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _load_refine_prompt(name: str, language: str) -> str:
    path = resolve_prompt_path("refine", f"{name}_{language}", language)
    return Path(path).read_text(encoding="utf-8").strip() + "\n"


def _single_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
