from __future__ import annotations

from pathlib import Path

from arc.orchestrator import ARCOrchestrator


def run_debate(
    idea_file: str,
    proposer_model: str,
    skeptic_model: str,
    moderator_model: str,
    output_dir: str = "reports",
) -> tuple[Path, Path]:
    orchestrator = ARCOrchestrator()
    return orchestrator.run(
        idea_file=idea_file,
        proposer_model=proposer_model,
        skeptic_model=skeptic_model,
        moderator_model=moderator_model,
        output_dir=output_dir,
    )
