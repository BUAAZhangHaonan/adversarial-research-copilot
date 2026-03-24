from __future__ import annotations

from pathlib import Path
import tomllib


def test_readme_matches_version_and_default_runtime_contract() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    readme = Path("README.md").read_text(encoding="utf-8")

    assert f"v{version}" in readme
    assert "当前默认配置不强制 Proposer 与 Skeptic 使用不同模型" in readme
    assert "reports/LATEST_RUN" in readme


def test_skill_docs_match_runtime_artifact_names() -> None:
    skills_readme = Path("skills/README.md").read_text(encoding="utf-8")
    debate_runner = Path("skills/debate-runner/SKILL.md").read_text(encoding="utf-8")
    idea_creator = Path("skills/idea-creator/SKILL.md").read_text(encoding="utf-8")
    novelty_check = Path("skills/novelty-check/SKILL.md").read_text(encoding="utf-8")
    experiment_bridge = Path("skills/experiment-bridge/SKILL.md").read_text(encoding="utf-8")

    assert "debate_log.jsonl" in skills_readme
    assert "research_decision_memo.md" in skills_readme
    assert "DEBATE_LOG.md" not in skills_readme
    assert "REVIEW_STATE.json" not in skills_readme

    assert "debate_log.jsonl" in debate_runner
    assert "research_decision_memo.md" in debate_runner
    assert "reports/latest" not in debate_runner

    assert "IDEA_REPORT.md" in idea_creator
    assert "IDEA_CANDIDATES.md" not in idea_creator

    assert "FINAL_PROPOSAL.md" in novelty_check
    assert "NOVELTY_CHECK.md" not in novelty_check

    assert "EXPERIMENT_PLAN.md" in experiment_bridge
    assert "当前实现只保证产出 `EXPERIMENT_PLAN.md`" in experiment_bridge
