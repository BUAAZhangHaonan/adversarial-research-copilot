from __future__ import annotations

import os

import typer
from rich.console import Console

from arc.runners.debate_runner import run_debate

app = typer.Typer(help="ARC - Adversarial Research Copilot")
console = Console()


@app.command()
def run(
    idea_file: str = typer.Argument(..., help="Path to idea markdown/text file"),
    proposer: str = typer.Option(
        os.getenv("ARC_DEFAULT_PROPOSER", "claude-sonnet-4-6"),
        help="Model for Proposer",
    ),
    skeptic: str = typer.Option(
        os.getenv("ARC_DEFAULT_SKEPTIC", "gpt-5.4"),
        help="Model for Skeptic",
    ),
    moderator: str = typer.Option(
        os.getenv("ARC_DEFAULT_MODERATOR", "gpt-5.4"),
        help="Model for Moderator",
    ),
    output_dir: str = typer.Option("reports", help="Output directory"),
    resume: bool = typer.Option(False, help="Resume from reports/latest/run_state.json if available"),
) -> None:
    report_file, state_file = run_debate(
        idea_file=idea_file,
        proposer_model=proposer,
        skeptic_model=skeptic,
        moderator_model=moderator,
        output_dir=output_dir,
        resume=resume,
    )
    console.print(f"[bold green]Report:[/bold green] {report_file}")
    console.print(f"[bold green]State:[/bold green] {state_file}")


if __name__ == "__main__":
    app()
