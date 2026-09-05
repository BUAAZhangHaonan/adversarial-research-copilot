from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from arc.runners import chat_mode_runner as cmr


def _base_config(**overrides) -> cmr.ChatModeConfig:
    defaults = dict(
        min_rounds_before_stop=1,
        max_rounds=2,
        min_references=1,
        max_response_chars=3200,
        max_paragraphs=3,
        export_best_consensus=False,
        persist_state=True,
        prompt_language="en",
        drift_check_interval=5,
        max_review_cycles=1,
        max_inner_debate_rounds=2,
    )
    defaults.update(overrides)
    return cmr.ChatModeConfig(**defaults)


def _setup_common_mocks(monkeypatch, tmp_path, *, resume=False, config_overrides=None):
    """Common mock setup for chat mode tests."""
    cfg = _base_config(**(config_overrides or {}))

    monkeypatch.setattr(cmr, "_load_chat_mode_config", lambda: cfg)
    monkeypatch.setattr(cmr, "LLMClient", lambda: object())
    monkeypatch.setattr(
        cmr,
        "_collect_chat_references",
        lambda topic, min_references: [
            {
                "source": "stub",
                "title": "Stub Paper",
                "abstract": "stub abstract",
                "year": 2026,
                "citation_count": 1,
            }
        ],
    )
    monkeypatch.setattr(
        cmr, "load_skills_dir",
        lambda d: {},
    )
    # Mock _run_pre_debate_stage to just create output files
    def fake_run_stage(stage_name, run_dir, client, models, skills, topic, cfg):
        stage_files = {
            "literature-research": ["REFERENCES.md", "LITERATURE_MAP.md"],
            "idea-creation": ["IDEA_REPORT.md"],
            "novelty-check": ["FINAL_PROPOSAL.md"],
            "evidence-grounding": ["EVIDENCE_TABLE.md"],
            "research-refine": [],
            "experiment-bridge": ["EXPERIMENT_PLAN.md"],
            "auto-review": ["AUTO_REVIEW.md", "RESEARCH_DECISION_MEMO.md"],
            "memo-synthesis": [],
        }
        for fname in stage_files.get(stage_name, []):
            if not (run_dir / fname).exists():
                (run_dir / fname).write_text(f"Fake {stage_name} output\n", encoding="utf-8")

    monkeypatch.setattr(cmr, "_run_pre_debate_stage", fake_run_stage)

    # Mock agents
    monkeypatch.setattr(
        cmr, "DriftMonitorAgent",
        lambda *a, **kw: type("MockDriftMonitor", (), {"run": lambda self, **k: "drift_detected: false\ndrift_severity: NONE\ncorrection: ''"})(),
    )
    monkeypatch.setattr(
        cmr, "ReviewerAgent",
        lambda *a, **kw: type("MockReviewer", (), {"run": lambda self, **k: "Review complete.\n```yaml\nreview_decision: RESOLVED\nunresolved_issues: []\npriority_actions: []\n```"})(),
    )


def test_chat_mode_resume_preserves_existing_rounds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    run_dir = reports_dir / "chat-run"
    run_dir.mkdir(parents=True)
    existing_round = {
        "round_id": 1,
        "proposer": "old proposer round 1",
        "skeptic": "old skeptic round 1",
        "moderator": "old moderator round 1",
        "judge_decision": "CONTINUE",
    }
    (run_dir / "chat_mode_state.json").write_text(
        json.dumps(
            {
                "topic": "topic",
                "rounds": [existing_round],
                "models": {
                    "proposer": "p",
                    "skeptic": "s",
                    "moderator": "m",
                },
                "config": {
                    "min_rounds_before_stop": 1,
                    "max_rounds": 2,
                    "max_response_chars": 3200,
                    "max_paragraphs": 3,
                    "export_best_consensus": False,
                },
                "reference_count": 1,
                "stop_reason": "in_progress",
                "status": "in_progress",
                "stage_statuses": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _setup_common_mocks(monkeypatch, tmp_path)

    def fake_chat_generate(client, model, role_prompt_path, user_prompt, max_chars, max_paragraphs, language):
        match = re.search(r"Round (\d+)", user_prompt)
        assert match is not None
        round_id = int(match.group(1))
        role = Path(role_prompt_path).stem
        if "moderator" in role:
            return f"Moderator summary\n[JUDGE_DECISION]: STOP_CONVERGED"
        return f"{role} generated round {round_id}"

    monkeypatch.setattr(cmr, "_chat_generate", fake_chat_generate)

    transcript_file, state_file = cmr.run_chat_mode(
        topic="topic",
        proposer_model="p",
        skeptic_model="s",
        moderator_model="m",
        output_dir=str(reports_dir),
        run_dir=str(run_dir),
        resume=True,
    )

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert [item["round_id"] for item in state["rounds"]] == [1, 2]
    assert state["rounds"][0]["proposer"] == "old proposer round 1"
    assert "old proposer round 1" in transcript_file.read_text(encoding="utf-8")


def test_chat_mode_resume_rejects_stale_in_progress_state(tmp_path: Path) -> None:
    run_dir = tmp_path / "reports" / "chat-run"
    run_dir.mkdir(parents=True)
    (run_dir / "chat_mode_state.json").write_text(
        json.dumps(
            {
                "topic": "topic",
                "rounds": [],
                "models": {
                    "proposer": "p",
                    "skeptic": "s",
                    "moderator": "m",
                },
                "status": "in_progress",
                "timestamp": "2020-01-01T00:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    state, resumed = cmr._load_chat_resume_state(
        run_dir,
        topic="topic",
        models={"proposer": "p", "skeptic": "s", "moderator": "m"},
        resume=True,
        max_stale_hours=24,
    )

    assert state is None
    assert resumed is False


def test_parse_judge_decision_does_not_false_stop_on_wording() -> None:
    text = "Current evidence is not sufficient yet; continue the next round."
    assert cmr._parse_judge_decision(text) == "CONTINUE"


def test_debate_prompt_builders_truncate_oversized_role_outputs() -> None:
    """Role outputs above _DEBATE_FIELD_MAX must be truncated in downstream prompts."""
    huge = "x" * (cmr._DEBATE_FIELD_MAX + 500)

    skeptic_prompt = cmr._build_skeptic_user_prompt(
        round_id=1, topic="t", reference_brief="refs",
        proposer_output=huge, min_references=1, language="en",
    )
    assert "...[truncated]" in skeptic_prompt
    assert huge not in skeptic_prompt

    moderator_prompt = cmr._build_moderator_user_prompt(
        round_id=1, topic="t", proposer_output=huge, skeptic_output=huge,
        language="en",
    )
    assert moderator_prompt.count("...[truncated]") == 2
    assert huge not in moderator_prompt


def test_parse_judge_decision_without_tag_returns_continue_no_tag() -> None:
    text = "Current evidence is not sufficient yet."
    assert cmr._parse_judge_decision(text) == "CONTINUE_NO_TAG"


def test_effective_round_bounds_zero_means_unlimited() -> None:
    cfg = _base_config(max_review_cycles=0, max_inner_debate_rounds=0)
    max_cycles, max_inner = cmr._effective_round_bounds(cfg)
    assert max_cycles >= cmr._UNLIMITED_ROUNDS
    assert max_inner >= cmr._UNLIMITED_ROUNDS

    cfg = _base_config(max_review_cycles=3, max_inner_debate_rounds=7)
    assert cmr._effective_round_bounds(cfg) == (3, 7)


def test_ensure_chat_references_reuses_cache_without_recollecting(tmp_path: Path) -> None:
    calls = {"count": 0}

    def fake_collect(topic, min_references):
        calls["count"] += 1
        return [{"source": "stub", "title": "Cached Paper", "abstract": "a", "year": 2026}]

    orig = cmr._collect_chat_references
    cmr._collect_chat_references = fake_collect
    try:
        first = cmr._ensure_chat_references(tmp_path, "topic", 1)
        assert first[0]["title"] == "Cached Paper"
        assert (tmp_path / "references_raw.json").exists()

        # Simulate collector failure: cache must serve the second call.
        def exploding(topic, min_references):
            raise RuntimeError("network down")

        cmr._collect_chat_references = exploding
        second = cmr._ensure_chat_references(tmp_path, "topic", 1)
        assert second == first
        assert calls["count"] == 1
    finally:
        cmr._collect_chat_references = orig


def test_chat_mode_survives_final_consensus_export_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"

    _setup_common_mocks(
        monkeypatch, tmp_path,
        config_overrides={"max_rounds": 1, "export_best_consensus": True},
    )

    def fake_chat_generate(client, model, role_prompt_path, user_prompt, max_chars, max_paragraphs, language):
        role = Path(role_prompt_path).stem
        if "moderator" in role:
            return "Moderator summary\n[JUDGE_DECISION]: STOP_CONVERGED"
        return f"{role} output"

    monkeypatch.setattr(cmr, "_chat_generate", fake_chat_generate)

    def exploding(*args, **kwargs):
        raise RuntimeError("api down")

    monkeypatch.setattr(cmr, "_export_best_consensus", exploding)

    transcript_file, state_file = cmr.run_chat_mode(
        topic="smoke topic",
        proposer_model="p",
        skeptic_model="s",
        moderator_model="m",
        output_dir=str(reports_dir),
        resume=False,
    )

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    # Interim consensus draft written during the debate must be retained.
    assert (transcript_file.parent / "BEST_CONSENSUS.md").exists()


def test_chat_mode_smoke_generates_references_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"

    _setup_common_mocks(monkeypatch, tmp_path, config_overrides={"max_rounds": 1})

    def fake_chat_generate(client, model, role_prompt_path, user_prompt, max_chars, max_paragraphs, language):
        role = Path(role_prompt_path).stem
        if "moderator" in role:
            return "Moderator summary\n[JUDGE_DECISION]: STOP_CONVERGED"
        return f"{role} output"

    monkeypatch.setattr(cmr, "_chat_generate", fake_chat_generate)

    transcript_file, state_file = cmr.run_chat_mode(
        topic="smoke topic",
        proposer_model="p",
        skeptic_model="s",
        moderator_model="m",
        output_dir=str(reports_dir),
        resume=False,
    )

    run_dir = transcript_file.parent
    refs_file = run_dir / "REFERENCES.md"
    assert transcript_file.exists()
    assert state_file.exists()
    assert refs_file.exists()
    assert "Stub Paper" in refs_file.read_text(encoding="utf-8")


def test_reviewer_feedback_reaches_next_cycle_proposer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cycle-1 reviewer feedback must appear in cycle-2 proposer prompts (review R3)."""
    reports_dir = tmp_path / "reports"

    _setup_common_mocks(
        monkeypatch, tmp_path,
        config_overrides={
            "max_rounds": 0,  # disable advisory target
            "max_review_cycles": 2,
            "max_inner_debate_rounds": 1,
            "min_rounds_before_stop": 1,
        },
    )

    marker = "UNIQUE-REVIEWER-MARKER-42"
    reviewer_calls = {"count": 0}

    def fake_reviewer_factory(*a, **kw):
        class StatefulReviewer:
            def run(self, **kwargs):
                reviewer_calls["count"] += 1
                if reviewer_calls["count"] == 1:
                    return (
                        "Cycle 1 unresolved.\n```yaml\n"
                        f"review_decision: UNRESOLVED\nunresolved_issues:\n  - {marker}\n"
                        "priority_actions: []\n```"
                    )
                # Second call should also have received the prior feedback.
                reviewer_calls["prior_feedback_seen"] = str(kwargs.get("prior_reviewer_feedback", ""))
                return "Resolved.\n```yaml\nreview_decision: RESOLVED\nunresolved_issues: []\n```"
        return StatefulReviewer()

    monkeypatch.setattr(cmr, "ReviewerAgent", fake_reviewer_factory)

    proposer_prompts: list[str] = []

    def fake_chat_generate(client, model, role_prompt_path, user_prompt, max_chars, max_paragraphs, language):
        role = Path(role_prompt_path).stem
        if "proposer" in role:
            proposer_prompts.append(user_prompt)
        if "moderator" in role:
            return "Moderator summary\n[JUDGE_DECISION]: STOP_CONVERGED"
        return f"{role} output"

    monkeypatch.setattr(cmr, "_chat_generate", fake_chat_generate)

    cmr.run_chat_mode(
        topic="feedback topic",
        proposer_model="p",
        skeptic_model="s",
        moderator_model="m",
        output_dir=str(reports_dir),
        resume=False,
    )

    assert len(proposer_prompts) >= 2, "expected two review cycles"
    assert marker not in proposer_prompts[0], "cycle 1 has no prior feedback yet"
    assert marker in proposer_prompts[1], "cycle 2 proposer must receive cycle 1 reviewer feedback"
    assert marker in reviewer_calls["prior_feedback_seen"], (
        "reviewer must see its own prior feedback when re-reviewing")


def test_max_rounds_is_a_hard_cap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """max_rounds must bound total rounds even when the judge always CONTINUEs
    and the reviewer always UNRESOLVEDs (review R9)."""
    reports_dir = tmp_path / "reports"

    _setup_common_mocks(
        monkeypatch, tmp_path,
        config_overrides={
            "max_rounds": 3,
            "min_rounds_before_stop": 1,
            "max_review_cycles": 5,
            "max_inner_debate_rounds": 10,
        },
    )

    reviewer_calls = {"count": 0}

    def unresolving_reviewer_factory(*a, **kw):
        class AlwaysUnresolved:
            def run(self, **kwargs):
                reviewer_calls["count"] += 1
                return "```yaml\nreview_decision: UNRESOLVED\nunresolved_issues:\n  - keep going\n```"
        return AlwaysUnresolved()

    monkeypatch.setattr(cmr, "ReviewerAgent", unresolving_reviewer_factory)

    def always_continue(client, model, role_prompt_path, user_prompt, max_chars, max_paragraphs, language):
        if "moderator" in Path(role_prompt_path).stem:
            return "Moderator summary\n[JUDGE_DECISION]: CONTINUE"
        return "role output"

    monkeypatch.setattr(cmr, "_chat_generate", always_continue)

    transcript_file, state_file = cmr.run_chat_mode(
        topic="cap topic",
        proposer_model="p", skeptic_model="s", moderator_model="m",
        output_dir=str(reports_dir), resume=False,
    )

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["rounds"]) == 3, "hard cap must bound total rounds"
    assert state["stop_reason"] == "max_rounds_hard_cap_3"
    assert reviewer_calls["count"] == 0, "no reviewer call after the hard cap fires"
