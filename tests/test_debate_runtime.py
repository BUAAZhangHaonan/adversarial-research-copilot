from __future__ import annotations

from pathlib import Path

import pytest

from arc.memory import DebateMemory
from arc.orchestrator import ARCOrchestrator
from arc.schemas import ScoreCard


def test_debate_resume_recovers_in_progress_round_after_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    idea_file = tmp_path / "idea.md"
    idea_file.write_text("test idea\n", encoding="utf-8")
    run_dir = tmp_path / "run"

    class StubAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, *args, **kwargs) -> str:
            return "stub output"

    monkeypatch.setattr("arc.orchestrator.ProposerAgent", StubAgent)
    monkeypatch.setattr("arc.orchestrator.SkepticAgent", StubAgent)
    monkeypatch.setattr("arc.orchestrator.ModeratorAgent", StubAgent)
    monkeypatch.setattr(
        "arc.orchestrator.parse_scorecard",
        lambda text: ScoreCard(
            novelty=4,
            feasibility=4,
            falsifiability=4,
            evaluation_clarity=4,
            resource_fit=4,
        ),
    )
    monkeypatch.setattr("arc.orchestrator.parse_decision", lambda text: "CONTINUE")
    monkeypatch.setattr(
        "arc.orchestrator.parse_unresolved_blockers",
        lambda text: ["missing baseline"],
    )
    monkeypatch.setattr(
        "arc.orchestrator.parse_required_revisions",
        lambda text: ["add stronger control"],
    )

    def interrupt_after_first_round(rounds, config):
        raise KeyboardInterrupt()

    monkeypatch.setattr("arc.orchestrator.assess_convergence", interrupt_after_first_round)

    orchestrator = ARCOrchestrator()

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run(
            idea_file=str(idea_file),
            proposer_model="p",
            skeptic_model="s",
            moderator_model="m",
            run_dir=run_dir,
        )

    memory = DebateMemory(run_dir)
    state, next_round, blockers, resumed = orchestrator._prepare_state(
        memory,
        idea="test idea",
        resume=True,
    )

    assert resumed is True
    assert len(state.rounds) == 1
    assert state.rounds[0].required_revisions == ["add stronger control"]
    assert next_round == 2
    assert blockers == ["missing baseline"]
