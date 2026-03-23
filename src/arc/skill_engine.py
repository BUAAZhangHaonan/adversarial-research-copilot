from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    argument_hint: str | None
    allowed_tools: list[str]
    body_markdown: str
    path: Path


class SkillLoadError(ValueError):
    pass


def load_skill(path: str | Path) -> Skill:
    p = Path(path)
    text = p.read_text(encoding="utf-8")

    frontmatter, body = _split_frontmatter(text)
    meta: dict[str, Any] = {}
    if frontmatter.strip():
        try:
            meta_obj = yaml.safe_load(frontmatter)
        except yaml.YAMLError as e:
            raise SkillLoadError(
                f"Invalid YAML frontmatter in {p}: {e}") from e
        if isinstance(meta_obj, dict):
            meta = meta_obj

    name = str(meta.get("name") or "").strip()
    if not name:
        raise SkillLoadError(f"Missing 'name' in YAML frontmatter: {p}")

    description = str(meta.get("description") or "").strip()
    argument_hint = meta.get("argument-hint")
    if isinstance(argument_hint, list):
        parts = [str(x).strip() for x in argument_hint if str(x).strip()]
        argument_hint = f"[{' '.join(parts)}]" if parts else None
    elif argument_hint is not None:
        argument_hint = str(argument_hint).strip() or None

    allowed_tools_raw = meta.get("allowed-tools")
    allowed_tools: list[str] = []
    if isinstance(allowed_tools_raw, list):
        allowed_tools = [str(x).strip()
                         for x in allowed_tools_raw if str(x).strip()]

    return Skill(
        name=name,
        description=description,
        argument_hint=argument_hint,
        allowed_tools=allowed_tools,
        body_markdown=body.strip() + "\n",
        path=p,
    )


def load_skills_dir(skills_dir: str | Path) -> dict[str, Skill]:
    root = Path(skills_dir)
    if not root.exists():
        raise FileNotFoundError(root)

    skills: dict[str, Skill] = {}
    for skill_file in root.glob("*/SKILL.md"):
        skill = load_skill(skill_file)
        if skill.name in skills:
            raise SkillLoadError(
                f"Duplicate skill name '{skill.name}' in {skill_file} and {skills[skill.name].path}")
        skills[skill.name] = skill
    return skills


def parse_stage_chain_from_pipeline_skill(pipeline_skill: Skill) -> list[str]:
    body = pipeline_skill.body_markdown
    lines = body.splitlines()

    start_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "## stage chain":
            start_idx = i + 1
            break

    if start_idx is None:
        raise SkillLoadError(
            f"pipeline skill {pipeline_skill.path} missing '## Stage Chain' section")

    stages: list[str] = []
    for line in lines[start_idx:]:
        s = line.strip()
        if not s:
            if stages:
                break
            continue
        if s.startswith("#"):
            break
        if s[0].isdigit() and "." in s:
            # '1. stage-name'
            part = s.split(".", 1)[1].strip()
            if part:
                stages.append(part.split()[0])
            continue
        if s.startswith("-"):
            part = s.lstrip("-").strip()
            if part:
                stages.append(part.split()[0])
            continue

    if not stages:
        raise SkillLoadError(
            f"pipeline skill {pipeline_skill.path} has empty Stage Chain")
    return stages


def _split_frontmatter(text: str) -> tuple[str, str]:
    # Expect optional YAML frontmatter at top delimited by '---' lines.
    # If absent, return empty frontmatter and full text as body.
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", text

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        # Treat as no frontmatter (avoid surprising truncation)
        return "", text

    front = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1:])
    return front, body
