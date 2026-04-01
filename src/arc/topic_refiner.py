from __future__ import annotations

import re
from dataclasses import dataclass

from arc.llm_client import LLMClient
from arc.prompting import localized_text, normalize_prompt_language


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
        writer_prompt = _writer_prompt(
            draft,
            previous_critique=history[-1].critique if history else None,
            language=language,
        )
        writer_output = client.chat(
            model=writer_model,
            system_prompt=_writer_system_prompt(language),
            user_prompt=writer_prompt,
            temperature=0.2,
        )
        refined = extract_refined_topic(writer_output)

        critique_output = client.chat(
            model=reviewer_model,
            system_prompt=_reviewer_system_prompt(language),
            user_prompt=_reviewer_prompt(refined, language),
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


def _writer_system_prompt(language: str) -> str:
    return localized_text(
        language,
        (
            "You are a research problem refiner. Produce output that is executable, falsifiable, and reproducible. "
            "Avoid vague vision statements and keep decisions test-oriented."
        ),
        (
            "你是研究题面优化器。你的输出必须让题目可实验、可证伪、可复现。"
            "避免空泛愿景，保持决策导向。"
        ),
    )


def _reviewer_system_prompt(language: str) -> str:
    return localized_text(
        language,
        (
            "You are a strict reviewer. Identify non-testable, non-executable, and non-reproducible parts, "
            "then propose the minimum repairs needed to unblock execution."
        ),
        (
            "你是严苛审稿人。找出题面中不可验证、不可执行、不可复现的部分，"
            "并给出最小修复动作。"
        ),
    )


def _writer_prompt(topic: str, previous_critique: str | None, language: str = "en") -> str:
    normalized = normalize_prompt_language(language)
    critique = previous_critique.strip() if previous_critique else localized_text(normalized, "none", "无")
    return localized_text(
        normalized,
        (
            "Refine the following research question into an execution-ready problem statement.\n"
            "Requirements:\n"
            "1) One-sentence title\n"
            "2) Clear task boundary\n"
            "3) Falsifiable hypothesis (H1/H0)\n"
            "4) Minimum experiment matrix (data, metrics, controls, failure criterion)\n"
            "5) Resource budget cap\n"
            "Start with heading '# Refined Topic' and put the final one-sentence title on the next line.\n\n"
            f"Original problem:\n{topic}\n\n"
            f"Previous review critique:\n{critique}\n"
        ),
        (
            "请将以下研究问题优化为可执行题面。\n"
            "要求：\n"
            "1) 一句话题目\n"
            "2) 明确任务边界\n"
            "3) 可证伪假设(H1/H0)\n"
            "4) 最小实验矩阵（数据、指标、对照、失败判据）\n"
            "5) 资源预算上限\n"
            "请先输出 '# 优化题面'，下一行给最终一句话题目。\n\n"
            f"原始问题：\n{topic}\n\n"
            f"上一轮审稿意见：\n{critique}\n"
        ),
    )


def _reviewer_prompt(refined: str, language: str = "en") -> str:
    normalized = normalize_prompt_language(language)
    return localized_text(
        normalized,
        (
            "Review whether the refined topic is execution-ready.\n"
            "Output four short sections:\n"
            "1) Critical defects\n"
            "2) Falsifiability check\n"
            "3) Minimum repair actions (3-5 items)\n"
            "4) Pipeline readiness decision (CONTINUE/STOP)\n\n"
            f"Refined topic:\n{refined}\n"
        ),
        (
            "请审查下述优化题面是否具备可执行性。\n"
            "输出四段：\n"
            "1) 关键缺陷\n"
            "2) 可证伪性检查\n"
            "3) 最小修复动作(3-5条)\n"
            "4) 是否可进入pipeline(CONTINUE/STOP)\n\n"
            f"题面：\n{refined}\n"
        ),
    )


def _single_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
