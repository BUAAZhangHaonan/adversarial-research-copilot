from __future__ import annotations

from pathlib import Path

import pytest

from arc.memory import DebateMemory
from arc.orchestrator import ARCOrchestrator
from arc.schemas import ScoreCard
import json


def test_debate_resume_recovers_in_progress_round_after_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    idea_file = tmp_path / "idea.md"
    idea_file.write_text("test idea\n", encoding="utf-8")
    reports_dir = tmp_path / "reports"
    run_dir = reports_dir / "run"

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
            output_dir=str(reports_dir),
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


def test_debate_resume_rejects_stale_state(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    memory = DebateMemory(run_dir)
    orchestrator = ARCOrchestrator()

    memory.save_json(
        "run_state.json",
        {
            "round": 1,
            "status": "in_progress",
            "blockers": ["stale blocker"],
            "timestamp": "2020-01-01T00:00:00+00:00",
        },
    )
    memory.save_json(
        "final_state.json",
        {
            "idea": "test idea",
            "framed_problem": "framed",
            "rounds": [],
        },
    )

    state, next_round, blockers, resumed = orchestrator._prepare_state(
        memory,
        idea="test idea",
        resume=True,
    )

    assert resumed is False
    assert next_round == 1
    assert blockers == []
    assert state.rounds == []


def test_debate_protocol_failure_retries_then_degrades_to_continue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Moderator output without valid continue_or_stop: one corrective retry,
    then parse_degraded=True and conservative CONTINUE (never a guessed STOP)."""
    idea_file = tmp_path / "idea.md"
    idea_file.write_text("test idea\n", encoding="utf-8")
    reports_dir = tmp_path / "reports"
    run_dir = reports_dir / "run"

    valid_output = (
        "Verdict text.\n```yaml\nscorecard:\n  novelty: 4\n  feasibility: 4\n"
        "  falsifiability: 4\n  evaluation_clarity: 4\n  resource_fit: 4\n"
        "unresolved_blockers: []\nrequired_revisions: []\n"
        "continue_or_stop: STOP\nreason: done\n```"
    )

    class ProtocolFlakyModerator:
        calls = {"count": 0}

        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, *args, **kwargs) -> str:
            ProtocolFlakyModerator.calls["count"] += 1
            if ProtocolFlakyModerator.calls["count"] == 1:
                return "Do not STOP; CONTINUE collecting evidence. (no yaml)"
            return valid_output

    class StubAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, *args, **kwargs) -> str:
            return "stub output"

    monkeypatch.setattr("arc.orchestrator.ProposerAgent", StubAgent)
    monkeypatch.setattr("arc.orchestrator.SkepticAgent", StubAgent)
    monkeypatch.setattr("arc.orchestrator.ModeratorAgent", ProtocolFlakyModerator)

    def interrupt(rounds, config):
        raise KeyboardInterrupt()

    monkeypatch.setattr("arc.orchestrator.assess_convergence", interrupt)

    orchestrator = ARCOrchestrator()
    with pytest.raises(KeyboardInterrupt):
        orchestrator.run(
            idea_file=str(idea_file),
            proposer_model="p", skeptic_model="s", moderator_model="m",
            output_dir=str(reports_dir), run_dir=run_dir,
        )

    final = json.loads((run_dir / "final_state.json").read_text(encoding="utf-8"))
    record = final["rounds"][0]
    assert record["decision"] == "STOP"  # recovered via the corrective retry
    assert record["parse_degraded"] is False
    assert ProtocolFlakyModerator.calls["count"] == 2


def test_debate_protocol_failure_after_retry_marks_degraded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    idea_file = tmp_path / "idea.md"
    idea_file.write_text("test idea\n", encoding="utf-8")
    reports_dir = tmp_path / "reports"
    run_dir = reports_dir / "run"

    class AlwaysBrokenModerator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, *args, **kwargs) -> str:
            return "I refuse to emit YAML. Do not STOP."

    class StubAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run(self, *args, **kwargs) -> str:
            return "stub output"

    monkeypatch.setattr("arc.orchestrator.ProposerAgent", StubAgent)
    monkeypatch.setattr("arc.orchestrator.SkepticAgent", StubAgent)
    monkeypatch.setattr("arc.orchestrator.ModeratorAgent", AlwaysBrokenModerator)

    def interrupt(rounds, config):
        raise KeyboardInterrupt()

    monkeypatch.setattr("arc.orchestrator.assess_convergence", interrupt)

    orchestrator = ARCOrchestrator()
    with pytest.raises(KeyboardInterrupt):
        orchestrator.run(
            idea_file=str(idea_file),
            proposer_model="p", skeptic_model="s", moderator_model="m",
            output_dir=str(reports_dir), run_dir=run_dir,
        )

    final = json.loads((run_dir / "final_state.json").read_text(encoding="utf-8"))
    record = final["rounds"][0]
    assert record["decision"] == "CONTINUE"  # conservative, never a guessed STOP
    assert record["parse_degraded"] is True
    run_state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["protocol_errors"] == 1
