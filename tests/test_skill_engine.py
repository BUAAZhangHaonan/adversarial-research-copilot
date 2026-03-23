from __future__ import annotations

from pathlib import Path

import pytest

from arc.skill_engine import SkillLoadError, load_skill, load_skills_dir, parse_stage_chain_from_pipeline_skill


def test_load_skill_parses_frontmatter_and_body(tmp_path: Path) -> None:
    p = tmp_path / "x" / "SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_text(
        """---
name: hello
description: test
argument-hint: [topic]
allowed-tools: [Read, Write]
---

# Body

Do something.
""",
        encoding="utf-8",
    )

    s = load_skill(p)
    assert s.name == "hello"
    assert s.description == "test"
    assert s.argument_hint == "[topic]"
    assert s.allowed_tools == ["Read", "Write"]
    assert "Do something" in s.body_markdown


def test_load_skills_dir_detects_duplicates(tmp_path: Path) -> None:
    a = tmp_path / "a" / "SKILL.md"
    b = tmp_path / "b" / "SKILL.md"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_text("---\nname: dup\n---\n\nA\n", encoding="utf-8")
    b.write_text("---\nname: dup\n---\n\nB\n", encoding="utf-8")

    with pytest.raises(SkillLoadError):
        load_skills_dir(tmp_path)


def test_parse_stage_chain_from_pipeline_skill(tmp_path: Path) -> None:
    p = tmp_path / "pipeline-arc" / "SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_text(
        """---
name: pipeline-arc
description: x
---

# ARC End-to-End Pipeline

## Stage Chain
1. research-lit
2. idea-creator
3. memo-synthesis

## Required Outputs
- X
""",
        encoding="utf-8",
    )

    pipeline = load_skill(p)
    chain = parse_stage_chain_from_pipeline_skill(pipeline)
    assert chain == ["research-lit", "idea-creator", "memo-synthesis"]
