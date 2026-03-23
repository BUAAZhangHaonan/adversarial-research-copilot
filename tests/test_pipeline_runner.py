from __future__ import annotations

from pathlib import Path

import pytest

from arc.runners.pipeline_runner import (
    PipelineError,
    _extract_auto_review_constants,
    _parse_auto_review_payload,
    _validate_stage_chain,
    run_pipeline,
)


class StubClient:
    def chat(self, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:  # noqa: D401
        # Deterministic output to avoid external API calls.
        return f"# OUT\n\nmodel={model}\n\n{user_prompt[:120]}\n"


def _write_skill(dir_: Path, name: str, body: str) -> None:
    p = dir_ / name / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nname: {name}\ndescription: test\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_pipeline_runs_minimal_chain(tmp_path: Path) -> None:
    # Create a minimal skills dir with a short pipeline chain that avoids debate.
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "pipeline-arc",
        """
## Stage Chain
1. research-lit
2. idea-creator
3. novelty-check
4. research-refine
5. experiment-bridge

""",
    )
    for stage in ["research-lit", "idea-creator", "novelty-check", "research-refine", "experiment-bridge"]:
        _write_skill(skills_dir, stage, f"# {stage}\n")

    state_file, memo_file = run_pipeline(
        topic="test topic",
        proposer_model="m1",
        skeptic_model="m2",
        moderator_model="m3",
        output_dir=str(tmp_path / "reports"),
        resume=False,
        skills_dir=str(skills_dir),
        client=StubClient(),
        strict_gates=False,
    )

    run_dir = state_file.parent
    assert state_file.exists()
    assert (run_dir / "LITERATURE_MAP.md").exists()
    assert (run_dir / "IDEA_REPORT.md").exists()
    assert (run_dir / "FINAL_PROPOSAL.md").exists()
    assert (run_dir / "EXPERIMENT_PLAN.md").exists()

    # Memo is always created at the end (placeholder if chain didn't produce one)
    assert memo_file.exists()


def test_pipeline_resume_skips_completed_stage(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "pipeline-arc",
        """
## Stage Chain
1. research-lit
2. idea-creator

""",
    )
    _write_skill(skills_dir, "research-lit", "# research-lit\n")
    _write_skill(skills_dir, "idea-creator", "# idea-creator\n")

    reports = tmp_path / "reports"

    first_state, _ = run_pipeline(
        topic="t",
        proposer_model="m1",
        skeptic_model="m2",
        moderator_model="m3",
        output_dir=str(reports),
        resume=False,
        skills_dir=str(skills_dir),
        client=StubClient(),
        strict_gates=False,
    )

    lit = first_state.parent / "LITERATURE_MAP.md"
    before = lit.read_text(encoding="utf-8")

    run_pipeline(
        topic="t",
        proposer_model="m1",
        skeptic_model="m2",
        moderator_model="m3",
        output_dir=str(reports),
        resume=True,
        skills_dir=str(skills_dir),
        client=StubClient(),
        strict_gates=False,
    )

    after = lit.read_text(encoding="utf-8")
    assert before == after


def test_extract_auto_review_constants() -> None:
    body = """
## Constants
- MAX_ROUNDS = 5
- POSITIVE_THRESHOLD = 8/10
"""
    constants = _extract_auto_review_constants(body)
    assert constants["MAX_ROUNDS"] == 5
    assert constants["POSITIVE_THRESHOLD"] == 8


def test_parse_auto_review_payload_yaml_and_revised_memo() -> None:
    text = """
```yaml
score_10: 8
top_blockers:
    - b1
required_changes:
    - c1
decision: STOP
```

# REVISED_MEMO

new memo content
"""
    parsed = _parse_auto_review_payload(text)
    assert parsed["score_10"] == 8
    assert parsed["decision"] == "STOP"
    assert parsed["top_blockers"] == ["b1"]
    assert parsed["required_changes"] == ["c1"]
    assert parsed["revised_memo"].startswith("new memo content")


def test_validate_stage_chain_requires_mandatory_gates() -> None:
    with pytest.raises(PipelineError):
        _validate_stage_chain(["research-lit", "novelty-check"])


def test_pipeline_can_disable_strict_gates(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "pipeline-arc",
        """
## Stage Chain
1. research-lit
2. idea-creator

""",
    )
    _write_skill(skills_dir, "research-lit", "# research-lit\n")
    _write_skill(skills_dir, "idea-creator", "# idea-creator\n")

    state_file, _ = run_pipeline(
        topic="t",
        proposer_model="m1",
        skeptic_model="m2",
        moderator_model="m3",
        output_dir=str(tmp_path / "reports"),
        resume=False,
        skills_dir=str(skills_dir),
        client=StubClient(),
        strict_gates=False,
    )
    assert state_file.exists()
