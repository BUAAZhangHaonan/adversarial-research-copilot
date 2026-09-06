from __future__ import annotations

from pathlib import Path

import yaml

from arc.llm_client import LLMClient
from arc.prompting import normalize_prompt_language, resolve_prompt_path


class ReviewerAgent:
    """Post-debate reviewer that evaluates the consensus document.

    In develop mode the reviewer produces a compact 3-paragraph response with a
    trailing YAML block containing ``review_decision``. In default mode the
    reviewer follows the full Pass 1 / Pass 2 structure with YAML output.
    """

    def __init__(self, client: LLMClient, model: str, prompt_language: str | None = None, *, mode: str = "develop") -> None:
        self.client = client
        self.model = model
        self.prompt_language = normalize_prompt_language(prompt_language)
        prompt_name = "reviewer"
        prompt_path = resolve_prompt_path(mode, prompt_name, self.prompt_language)
        self.system_prompt = Path(prompt_path).read_text(encoding="utf-8")

    def run(
        self,
        consensus_document: str,
        topic: str,
        review_cycle: int,
        prior_reviewer_feedback: str = "",
    ) -> str:
        feedback_section = ""
        if prior_reviewer_feedback:
            feedback_section = (
                "\n[PRIOR REVIEWER FEEDBACK]\n"
                f"{prior_reviewer_feedback}\n"
            )
        user_prompt = (
            f"Review cycle {review_cycle}.\n\n"
            "[RESEARCH TOPIC]\n"
            f"{topic}\n\n"
            "[CONSENSUS DOCUMENT]\n"
            f"{consensus_document}\n"
            f"{feedback_section}"
            "Follow your role contract exactly and include all required sections and YAML fields."
        )
        return self.client.chat(self.model, self.system_prompt, user_prompt, temperature=0.3)


def parse_reviewer_decision(text: str) -> dict:
    """Extract the reviewer's YAML verdict from the response.

    Returns a dict with at least ``review_decision`` (RESOLVED / UNRESOLVED).
    Falls back to keyword heuristics if no YAML block is found.
    """
    # Try fenced YAML block first
    for fence in ("```yaml", "```yml", "```"):
        idx = text.rfind(fence)
        if idx == -1:
            continue
        after = text[idx + len(fence):]
        end = after.find("```")
        if end == -1:
            continue
        yaml_str = after[:end].strip()
        try:
            data = yaml.safe_load(yaml_str)
            if isinstance(data, dict) and "review_decision" in data:
                return data
        except yaml.YAMLError:
            continue

    # Fallback: keyword heuristic
    lower = text.lower()
    if any(kw in lower for kw in ("no further questions", "no unresolved", "resolved", "proceed")):
        return {"review_decision": "RESOLVED"}
    return {"review_decision": "UNRESOLVED"}
