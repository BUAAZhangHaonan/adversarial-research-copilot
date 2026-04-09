from __future__ import annotations

from pathlib import Path

from arc.llm_client import LLMClient
from arc.prompting import normalize_prompt_language, resolve_prompt_path


class DriftMonitorAgent:
    """Lightweight topic-drift guardrail.

    Compares the current discussion trajectory against the original research
    topic and emits a short YAML verdict so the runner can inject corrections.
    """

    def __init__(self, client: LLMClient, model: str, prompt_language: str | None = None, *, mode: str = "chat") -> None:
        self.client = client
        self.model = model
        self.prompt_language = normalize_prompt_language(prompt_language)
        prompt_name = "drift_monitor_chat" if mode == "chat" else "drift_monitor"
        prompt_path = resolve_prompt_path(mode, prompt_name, self.prompt_language)
        self.system_prompt = Path(prompt_path).read_text(encoding="utf-8")

    def run(
        self,
        original_topic: str,
        current_summary: str,
        round_id: int,
    ) -> str:
        user_prompt = (
            f"Round {round_id} drift check.\n\n"
            "[ORIGINAL TOPIC]\n"
            f"{original_topic}\n\n"
            "[CURRENT DISCUSSION SUMMARY]\n"
            f"{current_summary}\n\n"
            "Respond with the YAML block described in your instructions."
        )
        return self.client.chat(self.model, self.system_prompt, user_prompt, temperature=0.2)
