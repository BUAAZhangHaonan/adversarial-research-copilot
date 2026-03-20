from __future__ import annotations

from pathlib import Path

from arc.schemas import ResearchState


def export_markdown_report(state: ResearchState, output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# ARC Research Decision Memo",
        "",
        "## Input Idea",
        state.idea,
        "",
        "## Framed Problem",
        state.framed_problem,
        "",
        "## Debate Rounds",
    ]

    for r in state.rounds:
        lines.extend(
            [
                f"### Round {r.round_id}",
                "",
                "#### Proposer",
                r.proposer,
                "",
                "#### Skeptic",
                r.skeptic,
                "",
                "#### Moderator",
                r.moderator,
                "",
                "#### Scorecard",
                f"- novelty: {r.scorecard.novelty}",
                f"- feasibility: {r.scorecard.feasibility}",
                f"- falsifiability: {r.scorecard.falsifiability}",
                f"- evaluation_clarity: {r.scorecard.evaluation_clarity}",
                f"- resource_fit: {r.scorecard.resource_fit}",
                f"- average: {r.scorecard.average:.2f}",
                "",
                "#### Unresolved Blockers",
            ]
        )
        if r.unresolved_blockers:
            lines.extend([f"- {b}" for b in r.unresolved_blockers])
        else:
            lines.append("- None")

        lines.extend(["", "#### Required Revisions"])
        if r.required_revisions:
            lines.extend([f"- {x}" for x in r.required_revisions])
        else:
            lines.append("- None")

        lines.extend(["", f"#### Decision: {r.decision}", ""])

    out.write_text("\n".join(lines), encoding="utf-8")
    return out
