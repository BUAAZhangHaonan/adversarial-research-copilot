from __future__ import annotations

from pathlib import Path

from arc.llm_client import LLMClient


class ProposerAgent:
    def __init__(self, client: LLMClient, model: str, prompt_path: str = "prompts/proposer.md") -> None:
        self.client = client
        self.model = model
        self.system_prompt = Path(prompt_path).read_text(encoding="utf-8")

    def run(
        self,
        framed_problem: str,
        previous_blockers: list[str],
        previous_required_revisions: list[str],
        round_id: int,
    ) -> str:
        blocker_text = "\n".join(f"- {b}" for b in previous_blockers) if previous_blockers else "- 无"
        revision_text = (
            "\n".join(f"- {r}" for r in previous_required_revisions)
            if previous_required_revisions
            else "- 无"
        )
        user_prompt = (
            f"第 {round_id} 轮。\n"
            f"问题框架：\n{framed_problem}\n\n"
            f"上一轮未解决 blockers：\n{blocker_text}\n\n"
            f"上一轮 required revisions：\n{revision_text}\n\n"
            "请严格按协议输出 6 个标题。"
        )
        return self.client.chat(self.model, self.system_prompt, user_prompt)
