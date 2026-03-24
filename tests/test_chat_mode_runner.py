from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from arc.runners import chat_mode_runner as cmr


def test_chat_mode_resume_preserves_existing_rounds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "chat-run"
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
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cmr,
        "_load_chat_mode_config",
        lambda: cmr.ChatModeConfig(
            min_rounds_before_stop=1,
            max_rounds=2,
            min_references=1,
            max_response_chars=3200,
            max_paragraphs=3,
            export_best_consensus=False,
            persist_state=True,
        ),
    )
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

    def fake_chat_generate(client, model, role_prompt_path, user_prompt, max_chars, max_paragraphs):
        match = re.search(r"Round (\d+)", user_prompt)
        assert match is not None
        round_id = int(match.group(1))
        role = Path(role_prompt_path).stem
        return f"{role} generated round {round_id}"

    monkeypatch.setattr(cmr, "_chat_generate", fake_chat_generate)

    transcript_file, state_file = cmr.run_chat_mode(
        topic="topic",
        proposer_model="p",
        skeptic_model="s",
        moderator_model="m",
        run_dir=str(run_dir),
        resume=True,
    )

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert [item["round_id"] for item in state["rounds"]] == [1, 2]
    assert state["rounds"][0]["proposer"] == "old proposer round 1"
    assert "old proposer round 1" in transcript_file.read_text(encoding="utf-8")
