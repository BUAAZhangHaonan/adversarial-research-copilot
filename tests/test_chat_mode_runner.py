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
