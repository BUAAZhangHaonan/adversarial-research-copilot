from __future__ import annotations

from pathlib import Path

from arc.llm_client import LLMClient
from arc.prompting import localized_text, normalize_prompt_language, resolve_prompt_path


class ProposerAgent:
    def __init__(self, client: LLMClient, model: str, prompt_language: str | None = None) -> None:
        self.client = client
        self.model = model
        self.prompt_language = normalize_prompt_language(prompt_language)
        prompt_path = resolve_prompt_path("default", "proposer", self.prompt_language)
        self.system_prompt = Path(prompt_path).read_text(encoding="utf-8")

    def run(
        self,
        framed_problem: str,
        previous_blockers: list[str],
        previous_required_revisions: list[str],
        round_id: int,
    ) -> str:
        blocker_text = "\n".join(
            f"- {b}" for b in previous_blockers) if previous_blockers else "- none"
        revision_text = (
            "\n".join(f"- {r}" for r in previous_required_revisions)
            if previous_required_revisions
            else "- none"
        )
        user_prompt = localized_text(
            self.prompt_language,
            (
                f"Round {round_id}.\n\n"
                "[PROBLEM FRAME]\n"
                f"{framed_problem}\n\n"
                "[UNRESOLVED BLOCKERS]\n"
                f"{blocker_text}\n\n"
                "[REQUIRED REVISIONS]\n"
                f"{revision_text}\n\n"
                "Follow your role contract exactly and include all required sections and YAML fields."
            ),
            (
                f"第 {round_id} 轮。\n\n"
                "[问题框架]\n"
                f"{framed_problem}\n\n"
                "[未解决 Blockers]\n"
                f"{blocker_text}\n\n"
                "[必须修订项]\n"
                f"{revision_text}\n\n"
                "请严格遵循角色协议，输出全部必需章节与 YAML 字段。"
            ),
        )
        return self.client.chat(self.model, self.system_prompt, user_prompt)
