from __future__ import annotations

from tests.helpers.text_contracts import assert_contains_all, read_text


PROMPT_MARKERS = {
    "prompts/latest/debate/proposer_en.md": [
        "Input Context You Will Receive",
        "Response to Prior Blockers / Revisions",
        "Machine-Readable Output",
        "proposal_quality:",
    ],
    "prompts/latest/debate/skeptic_en.md": [
        "Input Context You Will Receive",
        "Must-Answer Questions (Gate Conditions)",
        "Machine-Readable Output",
        "risk_summary:",
    ],
    "prompts/latest/debate/moderator_en.md": [
        "Input Context You Will Receive",
        "Verdict Logic",
        "Machine-Readable Output",
        "scorecard:",
    ],
    "prompts/latest/develop/proposer_en.md": [
        "Language policy:",
        "Length guidance:",
        "Commit to **one best path**",
        "Citations:",
    ],
    "prompts/latest/develop/skeptic_en.md": [
        "Language policy:",
        "Length guidance:",
        "at most 2 specific, concrete failure scenarios",
        "Evidence binding:",
    ],
    "prompts/latest/develop/moderator_en.md": [
        "Language policy:",
        "Length guidance:",
        "Mandatory final line",
        "[JUDGE_DECISION]:",
        "next_action: REASON | RETRIEVE | EXPERIMENT | STOP",
        "open_issues:",
        "stopping the discussion is NOT an endorsement",
    ],
    "prompts/latest/debate/proposer_zh.md": [
        "输入上下文",
        "机器可读 YAML",
        "proposal_quality:",
    ],
    "prompts/latest/debate/skeptic_zh.md": [
        "输入上下文",
        "机器可读 YAML",
        "risk_summary:",
    ],
    "prompts/latest/debate/moderator_zh.md": [
        "输入上下文",
        "机器可读 YAML",
        "scorecard:",
    ],
    "prompts/latest/develop/proposer_zh.md": [
        "必须使用中文自然表达",
        "最多 3 段",
    ],
    "prompts/latest/develop/skeptic_zh.md": [
        "必须使用中文自然表达",
        "2 个具体失败场景",
    ],
    "prompts/latest/develop/moderator_zh.md": [
        "必须使用中文自然表达",
        "[JUDGE_DECISION]:",
        "next_action: REASON | RETRIEVE | EXPERIMENT | STOP",
        "停止讨论不等于观点成立",
    ],
    "prompts/latest/debate/problem_framer_en.md": [
        "Input idea: {raw_idea}",
        "falsifiable",
    ],
    "prompts/latest/debate/problem_framer_zh.md": [
        "输入设想：{raw_idea}",
        "可证伪",
    ],
    "prompts/latest/develop/consensus_synthesizer_en.md": [
        "research lead",
    ],
    "prompts/latest/develop/consensus_task_en.md": [
        "Topic: {topic}",
        "first 3 execution steps",
    ],
    "prompts/latest/develop/consensus_task_zh.md": [
        "主题: {topic}",
        "最先执行的3步",
    ],
    "prompts/latest/refine/writer_task_en.md": [
        "{topic}",
        "{critique}",
        "# Refined Topic",
    ],
    "prompts/latest/refine/reviewer_task_zh.md": [
        "{refined}",
        "可证伪性检查",
    ],
    "prompts/latest/pipeline/auto_review_task.md": [
        "{threshold}/10",
        "{rid}/{max_rounds}",
        "REVISED_MEMO",
    ],
    "prompts/latest/discover/deep_read_question.md": [
        "VERIFIED CLAIMS",
        "LOAD-BEARING ASSUMPTIONS",
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
