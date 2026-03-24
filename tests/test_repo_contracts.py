from __future__ import annotations

import tomllib

from tests.helpers.text_contracts import assert_contains_all, assert_contains_none, read_text


def test_readme_matches_version_and_default_runtime_contract() -> None:
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    version = pyproject["project"]["version"]
    readme = read_text("README.md")

    assert_contains_all(
        readme,
        [f"v{version}", "当前默认配置不强制 Proposer 与 Skeptic 使用不同模型", "reports/LATEST_RUN"],
        label="README.md",
    )


def test_skill_docs_match_runtime_artifact_names() -> None:
    skills_readme = read_text("skills/README.md")
    debate_runner = read_text("skills/debate-runner/SKILL.md")
    idea_creator = read_text("skills/idea-creator/SKILL.md")
    novelty_check = read_text("skills/novelty-check/SKILL.md")
    experiment_bridge = read_text("skills/experiment-bridge/SKILL.md")

    assert_contains_all(
        skills_readme,
        ["debate_log.jsonl", "research_decision_memo.md"],
        label="skills/README.md",
    )
    assert_contains_none(
        skills_readme,
        ["DEBATE_LOG.md", "REVIEW_STATE.json"],
        label="skills/README.md",
    )

    assert_contains_all(
        debate_runner,
        ["debate_log.jsonl", "research_decision_memo.md"],
        label="skills/debate-runner/SKILL.md",
    )
    assert_contains_none(
        debate_runner,
        ["reports/latest"],
        label="skills/debate-runner/SKILL.md",
    )

    assert_contains_all(
        idea_creator,
        ["IDEA_REPORT.md"],
        label="skills/idea-creator/SKILL.md",
    )
    assert_contains_none(
        idea_creator,
        ["IDEA_CANDIDATES.md"],
        label="skills/idea-creator/SKILL.md",
    )

    assert_contains_all(
        novelty_check,
        ["FINAL_PROPOSAL.md"],
        label="skills/novelty-check/SKILL.md",
    )
    assert_contains_none(
        novelty_check,
        ["NOVELTY_CHECK.md"],
        label="skills/novelty-check/SKILL.md",
    )

    assert_contains_all(
        experiment_bridge,
        ["EXPERIMENT_PLAN.md", "当前实现只保证产出 `EXPERIMENT_PLAN.md`"],
        label="skills/experiment-bridge/SKILL.md",
    )
