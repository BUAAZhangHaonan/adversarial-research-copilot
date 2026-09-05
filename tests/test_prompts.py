from __future__ import annotations

from tests.helpers.text_contracts import assert_contains_all, read_text


PROMPT_MARKERS = {
    "prompts/latest/default/proposer_en.md": [
        "Input Context You Will Receive",
        "Response to Prior Blockers / Revisions",
        "Machine-Readable Output",
        "proposal_quality:",
    ],
    "prompts/latest/default/skeptic_en.md": [
        "Input Context You Will Receive",
        "Must-Answer Questions (Gate Conditions)",
        "Machine-Readable Output",
        "risk_summary:",
    ],
    "prompts/latest/default/moderator_en.md": [
        "Input Context You Will Receive",
        "Verdict Logic",
        "Machine-Readable Output",
        "scorecard:",
    ],
    "prompts/latest/chat/proposer_chat_en.md": [
        "Language policy:",
        "Length guidance:",
        "Commit to **one best path**",
        "Citations:",
    ],
    "prompts/latest/chat/skeptic_chat_en.md": [
        "Language policy:",
        "Length guidance:",
        "at most 2 specific, concrete failure scenarios",
        "Evidence binding:",
    ],
    "prompts/latest/chat/moderator_chat_en.md": [
        "Language policy:",
        "Length guidance:",
        "Mandatory final line",
        "[JUDGE_DECISION]:",
    ],
    "prompts/latest/default/proposer_zh.md": [
        "输入上下文",
        "机器可读 YAML",
        "proposal_quality:",
    ],
    "prompts/latest/default/skeptic_zh.md": [
        "输入上下文",
        "机器可读 YAML",
        "risk_summary:",
    ],
    "prompts/latest/default/moderator_zh.md": [
        "输入上下文",
        "机器可读 YAML",
        "scorecard:",
    ],
    "prompts/latest/chat/proposer_chat_zh.md": [
        "必须使用中文自然表达",
        "最多 3 段",
    ],
    "prompts/latest/chat/skeptic_chat_zh.md": [
        "必须使用中文自然表达",
        "2 个具体失败场景",
    ],
    "prompts/latest/chat/moderator_chat_zh.md": [
        "必须使用中文自然表达",
        "[JUDGE_DECISION]:",
    ],
    "prompts/latest/discover/theme_framer.md": [
        "Cognitive task",
        "Anti-patterns",
        "theme:",
        "search_queries:",
    ],
    "prompts/latest/discover/gap_miner.md": [
        "Cognitive task",
        "Judgment anchors",
        "Anti-patterns",
        "gaps:",
        "evidence_ids:",
        "question:",
    ],
    "prompts/latest/discover/saturation_auditor.md": [
        "Cognitive task",
        "audits:",
        "INSUFFICIENT_EVIDENCE",
        "evidence_basis:",
        "missing_evidence:",
        "verdict:",
    ],
    "prompts/latest/discover/duplicate_checker.md": [
        "Cognitive task",
        "checks:",
        "novelty_verdict:",
        "POSSIBLY_DUPLICATE",
        "differentiation:",
    ],
    "prompts/latest/discover/idea_generator.md": [
        "Cognitive task",
        "ideas:",
        "one_sentence_problem:",
        "minimal_falsifiable_test:",
        "anti_scope:",
    ],
    "prompts/latest/discover/taste_judge.md": [
        "Knowledge gain",
        "kill_evidence_type",
        "delta_type:",
        "judgments:",
        "priority:",
        "verdict:",
    ],
}


def test_prompt_contract_markers_present() -> None:
    for path_str, markers in PROMPT_MARKERS.items():
        text = read_text(path_str)
        assert_contains_all(text, markers, label=path_str)


def test_prompt_contract_doc_exists() -> None:
    text = read_text("docs/prompt-contracts.md")
    assert_contains_all(
        text,
        ["Debate Prompts", "Chat Mode Prompts", "Runtime-Owned Contract Fields"],
        label="docs/prompt-contracts.md",
    )
