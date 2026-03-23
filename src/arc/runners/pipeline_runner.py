from __future__ import annotations

import re
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from arc.llm_client import LLMClient
from arc.memory import DebateMemory
from arc.run_paths import resolve_run_dir
from arc.runners.debate_runner import run_debate
from arc.schemas import DebateConfig, PipelineStageRecord, PipelineState
from arc.skill_engine import Skill, SkillLoadError, load_skills_dir, parse_stage_chain_from_pipeline_skill


class PipelineError(RuntimeError):
    pass


def run_pipeline(
    topic: str,
    proposer_model: str,
    skeptic_model: str,
    moderator_model: str,
    output_dir: str = "reports",
    resume: bool = False,
    skills_dir: str = "skills",
    client: LLMClient | None = None,
    strict_gates: bool = True,
    human_checkpoint: bool = False,
) -> tuple[Path, Path]:
    """Run ARC pipeline in a skill-first style.

    Returns: (pipeline_state_file, final_memo_file)
    """

    run_dir = resolve_run_dir(output_dir, resume, "pipeline_state.json")

    memory = DebateMemory(run_dir)
    debate_cfg = _load_debate_config()

    pipeline_state = _prepare_pipeline_state(memory, topic, resume, debate_cfg)

    skills: dict[str, Skill] = load_skills_dir(skills_dir)
    if "pipeline-arc" not in skills:
        raise SkillLoadError("Missing skills/pipeline-arc/SKILL.md (skill name must be 'pipeline-arc')")

    stage_chain = parse_stage_chain_from_pipeline_skill(skills["pipeline-arc"])
    if strict_gates:
        _validate_stage_chain(stage_chain)

    # Ensure state has stage records (and keeps existing completion info on resume)
    pipeline_state = _ensure_stage_records(pipeline_state, stage_chain)
    _save_pipeline_state(memory, pipeline_state)

    client = client or LLMClient()

    for stage_name in stage_chain:
        record = pipeline_state.stage(stage_name)
        if record.status == "completed":
            continue

        record.status = "in_progress"
        record.started_at = datetime.now(UTC)
        pipeline_state.current_stage = stage_name
        _save_pipeline_state(memory, pipeline_state)

        try:
            _run_stage(
                stage_name=stage_name,
                topic=topic,
                resume=resume,
                proposer_model=proposer_model,
                skeptic_model=skeptic_model,
                moderator_model=moderator_model,
                run_dir=run_dir,
                memory=memory,
                client=client,
                skills=skills,
                pipeline_state=pipeline_state,
            )
            record.status = "completed"
            record.ended_at = datetime.now(UTC)
            record.error = None
        except KeyboardInterrupt:
            record.status = "failed"
            record.ended_at = datetime.now(UTC)
            record.error = "Interrupted"
            pipeline_state.status = "in_progress"
            _save_pipeline_state(memory, pipeline_state)
            raise
        except Exception as e:
            record.status = "failed"
            record.ended_at = datetime.now(UTC)
            record.error = f"{type(e).__name__}: {e}"
            pipeline_state.status = "failed"
            _save_pipeline_state(memory, pipeline_state)
            raise

        pipeline_state.status = "in_progress"
        _save_pipeline_state(memory, pipeline_state)

        if human_checkpoint and not _checkpoint_stage(stage_name):
            pipeline_state.status = "in_progress"
            _save_pipeline_state(memory, pipeline_state)
            raise KeyboardInterrupt(f"Stopped by human checkpoint at stage: {stage_name}")

    pipeline_state.status = "completed"
    pipeline_state.completed_at = datetime.now(UTC)
    _save_pipeline_state(memory, pipeline_state)

    memo = run_dir / "RESEARCH_DECISION_MEMO.md"
    if not memo.exists():
        memo.write_text(
            (
                f"# Research Decision Memo\n\n"
                f"Topic: {topic}\n\n"
                "Pipeline completed but no memo was produced by the stage chain.\n"
            ),
            encoding="utf-8",
        )
    return run_dir / "pipeline_state.json", memo


def _run_stage(
    stage_name: str,
    topic: str,
    resume: bool,
    proposer_model: str,
    skeptic_model: str,
    moderator_model: str,
    run_dir: Path,
    memory: DebateMemory,
    client: LLMClient,
    skills: dict[str, Skill],
    pipeline_state: PipelineState,
) -> None:
    # The stage contract is file-based. Each stage must create/overwrite its target output.
    if stage_name == "research-lit":
        out = run_dir / "LITERATURE_MAP.md"
        text = _llm_generate(
            client,
            model=proposer_model,
            system_prompt=_skill_body(skills, stage_name),
            user_prompt=(
                f"研究主题：{topic}\n\n"
                "请在不联网的前提下输出一个可执行的文献调研地图。\n"
                "要求：1) 列出关键子方向与关键词；2) 给出每个子方向的代表性论文类型/会议期刊；"
                "3) 明确假设与待验证清单；4) 输出为 Markdown。\n"
                f"目标文件：{out.name}"
            ),
        )
        out.write_text(text.strip() + "\n", encoding="utf-8")
        pipeline_state.stage(stage_name).outputs = [out.name]
        return

    if stage_name == "idea-creator":
        lit = _read_required(run_dir / "LITERATURE_MAP.md")
        out = run_dir / "IDEA_REPORT.md"
        text = _llm_generate(
            client,
            model=proposer_model,
            system_prompt=_skill_body(skills, stage_name),
            user_prompt=(
                "输入：LITERATURE_MAP.md\n\n"
                f"{lit}\n\n"
                "请基于输入生成多个研究 idea，并给出选择理由与风险。输出 Markdown。\n"
                f"目标文件：{out.name}"
            ),
        )
        out.write_text(text.strip() + "\n", encoding="utf-8")
        pipeline_state.stage(stage_name).inputs = ["LITERATURE_MAP.md"]
        pipeline_state.stage(stage_name).outputs = [out.name]
        return

    if stage_name == "novelty-check":
        idea = _read_required(run_dir / "IDEA_REPORT.md")
        out = run_dir / "FINAL_PROPOSAL.md"
        text = _llm_generate(
            client,
            model=skeptic_model,
            system_prompt=_skill_body(skills, stage_name),
            user_prompt=(
                "输入：IDEA_REPORT.md\n\n"
                f"{idea}\n\n"
                "请做严格 novelty 风险审查：列出最可能的先验工作、潜在重复点、需要证据的断言、以及如何区分。\n"
                "最后输出一个可提交到辩论环节的 FINAL_PROPOSAL（含评估标准与可证伪实验）。\n"
                f"目标文件：{out.name}"
            ),
        )
        out.write_text(text.strip() + "\n", encoding="utf-8")
        pipeline_state.stage(stage_name).inputs = ["IDEA_REPORT.md"]
        pipeline_state.stage(stage_name).outputs = [out.name]
        return

    if stage_name == "evidence-grounding":
        proposal = _read_required(run_dir / "FINAL_PROPOSAL.md")
        out = run_dir / "EVIDENCE_TABLE.md"
        text = _llm_generate(
            client,
            model=skeptic_model,
            system_prompt=_skill_body(skills, stage_name),
            user_prompt=(
                "输入：FINAL_PROPOSAL.md\n\n"
                f"{proposal}\n\n"
                "请将主张拆成可验证 claim，并输出证据表。若无法联网，请显式标注 unsupported 与待检索动作。\n"
                f"目标文件：{out.name}"
            ),
        )
        out.write_text(text.strip() + "\n", encoding="utf-8")
        pipeline_state.stage(stage_name).inputs = ["FINAL_PROPOSAL.md"]
        pipeline_state.stage(stage_name).outputs = [out.name]
        return

    if stage_name == "research-refine":
        proposal = _read_required(run_dir / "FINAL_PROPOSAL.md")
        out = run_dir / "FINAL_PROPOSAL.md"
        text = _llm_generate(
            client,
            model=proposer_model,
            system_prompt=_skill_body(skills, stage_name),
            user_prompt=(
                "输入：FINAL_PROPOSAL.md\n\n"
                f"{proposal}\n\n"
                "请在不引入新外部证据的前提下，按可实验验证/可证伪/资源约束，重写并强化提案。\n"
                "输出必须是完整的 FINAL_PROPOSAL（覆盖写）。\n"
                f"目标文件：{out.name}"
            ),
        )
        out.write_text(text.strip() + "\n", encoding="utf-8")
        pipeline_state.stage(stage_name).inputs = ["FINAL_PROPOSAL.md"]
        pipeline_state.stage(stage_name).outputs = [out.name]
        return

    if stage_name == "experiment-bridge":
        proposal = _read_required(run_dir / "FINAL_PROPOSAL.md")
        out = run_dir / "EXPERIMENT_PLAN.md"
        text = _llm_generate(
            client,
            model=proposer_model,
            system_prompt=_skill_body(skills, stage_name),
            user_prompt=(
                "输入：FINAL_PROPOSAL.md\n\n"
                f"{proposal}\n\n"
                "请产出实验计划（不执行），包括：数据/指标/对照/消融/失败判据/资源估算，以及脚本结构草案（伪代码即可）。\n"
                f"目标文件：{out.name}"
            ),
        )
        out.write_text(text.strip() + "\n", encoding="utf-8")
        pipeline_state.stage(stage_name).inputs = ["FINAL_PROPOSAL.md"]
        pipeline_state.stage(stage_name).outputs = [out.name]
        return

    if stage_name == "debate-runner":
        # Use FINAL_PROPOSAL.md as the idea input to existing debate engine.
        idea_file = str(run_dir / "FINAL_PROPOSAL.md")
        run_debate(
            idea_file=idea_file,
            proposer_model=proposer_model,
            skeptic_model=skeptic_model,
            moderator_model=moderator_model,
            output_dir=str(run_dir.parent),
            resume=resume,
            run_dir=str(run_dir),
        )
        src_memo = run_dir / "research_decision_memo.md"
        dst_memo = run_dir / "RESEARCH_DECISION_MEMO.md"
        if src_memo.exists():
            dst_memo.write_text(src_memo.read_text(encoding="utf-8"), encoding="utf-8")
        pipeline_state.stage(stage_name).inputs = ["FINAL_PROPOSAL.md"]
        pipeline_state.stage(stage_name).outputs = [dst_memo.name]
        return

    if stage_name == "auto-review-loop":
        memo_path = run_dir / "RESEARCH_DECISION_MEMO.md"
        _read_required(memo_path)
        log_path = run_dir / "AUTO_REVIEW.md"

        constants = _extract_auto_review_constants(_skill_body(skills, stage_name))
        max_rounds = constants["MAX_ROUNDS"]
        threshold = constants["POSITIVE_THRESHOLD"]
        stage_state_file = run_dir / "auto_review_state.json"
        round_start = 1
        if resume and stage_state_file.exists():
            try:
                st = json.loads(stage_state_file.read_text(encoding="utf-8"))
                if st.get("status") == "in_progress":
                    round_start = int(st.get("next_round", 1))
            except Exception:
                round_start = 1

        for rid in range(round_start, max_rounds + 1):
            memo = _read_required(memo_path)
            stage_state_file.write_text(
                json.dumps(
                    {
                        "status": "in_progress",
                        "next_round": rid,
                        "max_rounds": max_rounds,
                        "threshold": threshold,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            review = _llm_generate(
                client,
                model=skeptic_model,
                system_prompt=_skill_body(skills, stage_name),
                user_prompt=(
                    "你是严格审稿人。请输出如下结构：\n"
                    "1) 一个 YAML 代码块，键必须包含：score_10, top_blockers, required_changes, decision(仅 CONTINUE/STOP)\n"
                    "2) 紧接一个标题 '# REVISED_MEMO'，其后给出完整修订版 memo。\n"
                    "判停规则：若 score_10 >= 7 且关键 blocker 已清空，可给 STOP。\n\n"
                    f"当前阈值：{threshold}/10\n"
                    f"当前轮次：{rid}/{max_rounds}\n\n"
                    f"原始 memo：\n{memo}\n"
                ),
            )

            parsed = _parse_auto_review_payload(review)
            score_10 = parsed.get("score_10", 0)
            decision = str(parsed.get("decision", "CONTINUE")).upper()
            revised_memo = str(parsed.get("revised_memo", "")).strip()
            if revised_memo:
                memo_path.write_text(revised_memo + "\n", encoding="utf-8")

            prev = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
            log_path.write_text(
                prev
                + (
                    f"\n\n## Review Round {rid} ({datetime.now(UTC).isoformat()})\n\n"
                    f"- score_10: {score_10}\n"
                    f"- decision: {decision}\n"
                    f"- blockers: {parsed.get('top_blockers', [])}\n"
                    f"- changes: {parsed.get('required_changes', [])}\n\n"
                    "### Raw Review\n\n"
                    f"{review.strip()}\n"
                ),
                encoding="utf-8",
            )

            should_stop = decision == "STOP" or score_10 >= threshold
            if should_stop:
                stage_state_file.write_text(
                    json.dumps(
                        {
                            "status": "completed",
                            "next_round": rid + 1,
                            "max_rounds": max_rounds,
                            "threshold": threshold,
                            "final_score_10": score_10,
                            "final_decision": decision,
                            "updated_at": datetime.now(UTC).isoformat(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                break
        else:
            stage_state_file.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "next_round": max_rounds + 1,
                        "max_rounds": max_rounds,
                        "threshold": threshold,
                        "final_score_10": None,
                        "final_decision": "CONTINUE",
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        pipeline_state.stage(stage_name).inputs = [memo_path.name]
        pipeline_state.stage(stage_name).outputs = [memo_path.name, log_path.name, stage_state_file.name]
        return

    if stage_name == "memo-synthesis":
        # No-op synthesis in MVP: ensure memo exists.
        memo_path = run_dir / "RESEARCH_DECISION_MEMO.md"
        if not memo_path.exists():
            src = run_dir / "research_decision_memo.md"
            if src.exists():
                memo_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        pipeline_state.stage(stage_name).inputs = ["RESEARCH_DECISION_MEMO.md"]
        pipeline_state.stage(stage_name).outputs = ["RESEARCH_DECISION_MEMO.md"]
        return

    raise PipelineError(f"Unknown pipeline stage: {stage_name}")


def _llm_generate(client: LLMClient, model: str, system_prompt: str, user_prompt: str) -> str:
    return client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)


def _read_required(path: Path) -> str:
    if not path.exists():
        raise PipelineError(f"Missing required input: {path}")
    return path.read_text(encoding="utf-8")


def _skill_body(skills: dict[str, Skill], skill_name: str) -> str:
    skill = skills.get(skill_name)
    if skill is None:
        # Allow running even if a stage skill is absent; keep system prompt minimal.
        return "You are a rigorous research assistant. Follow the user instructions precisely."
    return getattr(skill, "body_markdown", "") or ""


def _load_debate_config(config_path: str | Path = "configs/debate.yaml") -> DebateConfig:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    return DebateConfig(**cfg.get("debate", {}))


def _prepare_pipeline_state(memory: DebateMemory, topic: str, resume: bool, debate_cfg: DebateConfig) -> PipelineState:
    if not resume:
        return PipelineState.new(topic=topic)

    state_obj = memory.load_json("pipeline_state.json")
    if not state_obj:
        return PipelineState.new(topic=topic)

    state = PipelineState.model_validate(state_obj)
    if state.status != "in_progress":
        return PipelineState.new(topic=topic)

    ts = state.updated_at
    now = datetime.now(UTC)
    age_hours = (now - ts).total_seconds() / 3600
    if age_hours > debate_cfg.stale_resume_hours:
        return PipelineState.new(topic=topic)

    return state


def _ensure_stage_records(state: PipelineState, stage_chain: list[str]) -> PipelineState:
    existing = {s.name: s for s in state.stages}
    stages: list[PipelineStageRecord] = []
    for name in stage_chain:
        if name in existing:
            stages.append(existing[name])
        else:
            stages.append(PipelineStageRecord(name=name))
    state.stages = stages
    return state


def _save_pipeline_state(memory: DebateMemory, state: PipelineState) -> None:
    state.updated_at = datetime.now(UTC)
    memory.save_json("pipeline_state.json", state.model_dump(mode="json"))


def _validate_stage_chain(stage_chain: list[str]) -> None:
    mandatory = ["novelty-check", "debate-runner"]
    missing = [x for x in mandatory if x not in stage_chain]
    if missing:
        raise PipelineError(
            "Stage chain missing mandatory gates: " + ", ".join(missing)
        )


def _checkpoint_stage(stage_name: str) -> bool:
    answer = input(f"[pipeline checkpoint] stage '{stage_name}' completed. Continue? [Y/n]: ").strip().lower()
    return answer in {"", "y", "yes"}


def _extract_auto_review_constants(skill_body: str) -> dict[str, int]:
    max_rounds = 4
    threshold = 7
    for line in skill_body.splitlines():
        s = line.strip()
        if s.startswith("- MAX_ROUNDS") and "=" in s:
            try:
                max_rounds = int(s.split("=", 1)[1].strip())
            except ValueError:
                pass
        if s.startswith("- POSITIVE_THRESHOLD") and "=" in s:
            raw = s.split("=", 1)[1].strip()
            if "/" in raw:
                left = raw.split("/", 1)[0].strip()
            else:
                left = raw
            try:
                threshold = int(left)
            except ValueError:
                pass
    return {"MAX_ROUNDS": max_rounds, "POSITIVE_THRESHOLD": threshold}


def _parse_auto_review_payload(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "score_10": 0,
        "top_blockers": [],
        "required_changes": [],
        "decision": "CONTINUE",
        "revised_memo": "",
    }

    yaml_block = _extract_fenced_yaml(text)
    if yaml_block:
        try:
            obj = yaml.safe_load(yaml_block)
            if isinstance(obj, dict):
                parsed["score_10"] = int(obj.get("score_10", 0) or 0)
                parsed["top_blockers"] = _to_str_list(obj.get("top_blockers"))
                parsed["required_changes"] = _to_str_list(obj.get("required_changes"))
                decision = str(obj.get("decision", "CONTINUE")).upper()
                parsed["decision"] = "STOP" if decision == "STOP" else "CONTINUE"
        except Exception:
            pass

    revised = _extract_revised_memo(text)
    if revised:
        parsed["revised_memo"] = revised
    else:
        parsed["revised_memo"] = text.strip()

    return parsed


def _extract_fenced_yaml(text: str) -> str:
    m = re.search(r"```(?:yaml|yml)\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_revised_memo(text: str) -> str:
    # Prefer heading-based extraction.
    m = re.search(r"^#\s*REVISED_MEMO\s*$", text, flags=re.MULTILINE | re.IGNORECASE)
    if m:
        return text[m.end() :].strip()
    # Fallback: remove YAML block and keep the rest.
    return re.sub(r"```(?:yaml|yml)\s*.*?```", "", text, flags=re.IGNORECASE | re.DOTALL).strip()


def _to_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    return [s] if s else []
