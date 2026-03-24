from __future__ import annotations

from tests.helpers.text_contracts import assert_contains_all, read_text


PROMPT_MARKERS = {
    "prompts/proposer.md": [
        "输入上下文：",
        "上一轮未解决 blockers / required revisions",
        "你必须主张一个首选方案",
        "机器可读 YAML",
        "proposal_quality:",
    ],
    "prompts/skeptic.md": [
        "输入上下文：",
        "Proposer 输出",
        "必须回答否则不放行的问题",
        "机器可读 YAML",
        "risk_summary:",
    ],
    "prompts/moderator.md": [
        "输入上下文：",
        "Proposer 输出",
        "Skeptic 输出",
        "机器可读 YAML",
        "scorecard:",
    ],
    "prompts/chat_mode/proposer_chat.md": [
        "必须使用中文自然表达",
        "最多 3 段",
        "优先推进一个最强主方案",
        "所有关键判断都要绑定参考文献",
    ],
    "prompts/chat_mode/skeptic_chat.md": [
        "必须使用中文自然表达",
        "最多 3 段",
        "至少给出 2 个具体失败场景",
        "所有关键反驳都要绑定参考文献",
    ],
    "prompts/chat_mode/moderator_chat.md": [
        "必须使用中文自然表达",
        "最多 3 段",
        "区分证据充分与证据不足的判断",
        "[JUDGE_DECISION]:",
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
