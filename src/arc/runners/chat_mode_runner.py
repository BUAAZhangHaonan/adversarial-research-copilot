from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from arc.llm_client import LLMClient
from arc.run_paths import resolve_run_dir
from arc.runners.pipeline_runner import _collect_references, _format_references


@dataclass
class ChatModeConfig:
    min_rounds_before_stop: int = 20
    # Use 0 for unlimited rounds (stop only by judge decision).
    max_rounds: int = 60
    min_references: int = 20
    # Approximate upper bound close to 1K tokens for most providers.
    max_response_chars: int = 3200
    max_paragraphs: int = 3
    export_best_consensus: bool = True
    persist_state: bool = True


def run_chat_mode(
    topic: str,
    proposer_model: str,
    skeptic_model: str,
    moderator_model: str,
    output_dir: str = "reports",
    resume: bool = False,
    run_dir: str | None = None,
    min_rounds_before_stop: int | None = None,
    max_rounds: int | None = None,
    export_best_consensus: bool | None = None,
) -> tuple[Path, Path]:
    cfg = _load_chat_mode_config()
    if min_rounds_before_stop is not None:
        cfg.min_rounds_before_stop = max(1, min_rounds_before_stop)
    if max_rounds is not None:
        cfg.max_rounds = int(max_rounds)
    if cfg.max_rounds < 0:
        cfg.max_rounds = 0
    if cfg.max_rounds > 0 and cfg.max_rounds < cfg.min_rounds_before_stop:
        cfg.max_rounds = cfg.min_rounds_before_stop
    if export_best_consensus is not None:
        cfg.export_best_consensus = export_best_consensus

    target_run_dir = Path(run_dir) if run_dir else resolve_run_dir(output_dir, resume, "chat_mode_state.json")
    state_file = target_run_dir / "chat_mode_state.json"
    resume_state, resumed = _load_chat_resume_state(
        target_run_dir,
        topic=topic,
        proposer_model=proposer_model,
        skeptic_model=skeptic_model,
        moderator_model=moderator_model,
        resume=resume,
        max_stale_hours=24,
    )
    if resume and run_dir is None and not resumed and state_file.exists():
        target_run_dir = resolve_run_dir(output_dir, False, "chat_mode_state.json")
        state_file = target_run_dir / "chat_mode_state.json"
        resume_state, resumed = _load_chat_resume_state(
            target_run_dir,
            topic=topic,
            proposer_model=proposer_model,
            skeptic_model=skeptic_model,
            moderator_model=moderator_model,
            resume=False,
            max_stale_hours=24,
        )
    target_run_dir.mkdir(parents=True, exist_ok=True)
    chat_dir = target_run_dir / "chat_rounds"
    chat_dir.mkdir(parents=True, exist_ok=True)

    client = LLMClient()
    refs = _collect_chat_references(topic, cfg.min_references)
    references_text = _format_references(refs)

    if resumed:
        existing_topic = (target_run_dir / "TOPIC_CHAT.txt").read_text(
            encoding="utf-8").strip() if (target_run_dir / "TOPIC_CHAT.txt").exists() else ""
        if existing_topic and existing_topic != topic.strip():
            raise RuntimeError(
                "Resume requested with a different topic than the in-progress chat run.")

    (target_run_dir / "TOPIC_CHAT.txt").write_text(topic.strip() + "\n", encoding="utf-8")
    (target_run_dir / "REFERENCES.md").write_text(references_text, encoding="utf-8")

    rounds: list[dict[str, Any]] = list(resume_state.get("rounds", [])) if resume_state else []
    prior_summary = _extract_summary_anchor(str(rounds[-1].get("moderator", ""))) if rounds else ""
    stop_reason = "running"
    reference_brief = _build_reference_brief(refs, max_items=cfg.min_references)
    start_round = max((int(item.get("round_id", 0)) for item in rounds), default=0) + 1

    round_id = start_round
    while True:
        if cfg.max_rounds > 0 and round_id > cfg.max_rounds:
            stop_reason = "max_rounds_reached"
            break
        proposer_output = _chat_generate(
            client=client,
            model=proposer_model,
            role_prompt_path="prompts/chat_mode/proposer_chat.md",
            user_prompt=(
                f"Round {round_id}. 研究主题: {topic}\n\n"
                f"参考文献摘要索引(至少{cfg.min_references}篇):\n{reference_brief}\n\n"
                f"上一轮裁判总结: {prior_summary or '无'}\n\n"
                "请直接给出你最有创新性、且可执行的方案路径，用聊天式表达，尝试说服反方。"
            ),
            max_chars=cfg.max_response_chars,
            max_paragraphs=cfg.max_paragraphs,
        )

        skeptic_output = _chat_generate(
            client=client,
            model=skeptic_model,
            role_prompt_path="prompts/chat_mode/skeptic_chat.md",
            user_prompt=(
                f"Round {round_id}. 研究主题: {topic}\n\n"
                f"参考文献摘要索引(至少{cfg.min_references}篇):\n{reference_brief}\n\n"
                f"正方观点:\n{proposer_output}\n\n"
                "请拼命找反例、边界条件和失败情境，聊天式表达，但结论要可操作。"
            ),
            max_chars=cfg.max_response_chars,
            max_paragraphs=cfg.max_paragraphs,
        )

        moderator_output = _chat_generate(
            client=client,
            model=moderator_model,
            role_prompt_path="prompts/chat_mode/moderator_chat.md",
            user_prompt=(
                f"Round {round_id}. 研究主题: {topic}\n\n"
                f"正方:\n{proposer_output}\n\n"
                f"反方:\n{skeptic_output}\n\n"
                "请作为裁判给出阶段判决、折中方案、下一轮聚焦问题。"
            ),
            max_chars=cfg.max_response_chars,
            max_paragraphs=cfg.max_paragraphs,
        )

        decision = _parse_judge_decision(moderator_output)
        round_record = {
            "round_id": round_id,
            "proposer": proposer_output,
            "skeptic": skeptic_output,
            "moderator": moderator_output,
            "judge_decision": decision,
        }
        rounds.append(round_record)
        prior_summary = _extract_summary_anchor(moderator_output)

        _write_round_artifacts(chat_dir, round_record)
        _write_chat_mode_state(
            state_file=state_file,
            topic=topic,
            rounds=rounds,
            proposer_model=proposer_model,
            skeptic_model=skeptic_model,
            moderator_model=moderator_model,
            cfg=cfg,
            reference_count=len(refs),
            stop_reason=stop_reason,
            status="in_progress",
        )

        if round_id >= cfg.min_rounds_before_stop and decision.startswith("STOP"):
            stop_reason = decision
            break

        round_id += 1

    transcript = _build_transcript(topic, rounds)
    transcript_file = target_run_dir / "CHAT_TRANSCRIPT.md"
    transcript_file.write_text(transcript, encoding="utf-8")

    consensus_file: Path | None = None
    if cfg.export_best_consensus:
        consensus_file = _export_best_consensus(
            client=client,
            model=moderator_model,
            topic=topic,
            rounds=rounds,
            refs=refs,
            output_file=target_run_dir / "BEST_CONSENSUS.md",
            max_chars=cfg.max_response_chars,
            max_paragraphs=cfg.max_paragraphs,
        )

    index_file = target_run_dir / "CHAT_MODE_INDEX.md"
    index_file.write_text(
        _build_index(target_run_dir, cfg, len(refs), rounds, stop_reason, consensus_file),
        encoding="utf-8",
    )

    if cfg.persist_state:
        _write_chat_mode_state(
            state_file=state_file,
            topic=topic,
            rounds=rounds,
            proposer_model=proposer_model,
            skeptic_model=skeptic_model,
            moderator_model=moderator_model,
            cfg=cfg,
            reference_count=len(refs),
            stop_reason=stop_reason,
            status="completed",
        )

    return transcript_file, state_file


def _load_chat_resume_state(
    run_dir: Path,
    topic: str,
    proposer_model: str,
    skeptic_model: str,
    moderator_model: str,
    resume: bool,
    max_stale_hours: int,
) -> tuple[dict[str, Any] | None, bool]:
    if not resume:
        return None, False

    state_file = run_dir / "chat_mode_state.json"
    if not state_file.exists():
        return None, False
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None, False

    if str(state.get("status", "")).strip().lower() != "in_progress":
        return None, False
    if str(state.get("topic", "")).strip() != topic.strip():
        return None, False

    models = state.get("models", {})
    if not isinstance(models, dict):
        return None, False
    if models.get("proposer") != proposer_model:
        return None, False
    if models.get("skeptic") != skeptic_model:
        return None, False
    if models.get("moderator") != moderator_model:
        return None, False

    timestamp = str(state.get("timestamp", "")).strip()
    if timestamp:
        try:
            updated_at = datetime.fromisoformat(timestamp)
        except ValueError:
            return None, False
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        age_hours = (datetime.now(UTC) - updated_at).total_seconds() / 3600
        if age_hours > max_stale_hours:
            return None, False

    rounds = state.get("rounds", [])
    if not isinstance(rounds, list):
        return None, False
    return state, True


def _write_chat_mode_state(
    state_file: Path,
    topic: str,
    rounds: list[dict[str, Any]],
    proposer_model: str,
    skeptic_model: str,
    moderator_model: str,
    cfg: ChatModeConfig,
    reference_count: int,
    stop_reason: str,
    status: str,
) -> None:
    state_file.write_text(
        json.dumps(
            {
                "topic": topic,
                "rounds": rounds,
                "models": {
                    "proposer": proposer_model,
                    "skeptic": skeptic_model,
                    "moderator": moderator_model,
                },
                "config": {
                    "min_rounds_before_stop": cfg.min_rounds_before_stop,
                    "max_rounds": cfg.max_rounds,
                    "max_response_chars": cfg.max_response_chars,
                    "max_paragraphs": cfg.max_paragraphs,
                    "export_best_consensus": cfg.export_best_consensus,
                },
                "reference_count": reference_count,
                "stop_reason": stop_reason,
                "status": status,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _load_chat_mode_config(config_path: str | Path = "configs/chat_mode.yaml") -> ChatModeConfig:
    defaults = ChatModeConfig()
    p = Path(config_path)
    if not p.exists():
        return defaults
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        cfg = data.get("chat_mode", {}) if isinstance(data, dict) else {}
        return ChatModeConfig(
            min_rounds_before_stop=max(1, int(cfg.get("min_rounds_before_stop", defaults.min_rounds_before_stop))),
            max_rounds=max(0, int(cfg.get("max_rounds", defaults.max_rounds))),
            min_references=max(20, int(cfg.get("min_references", defaults.min_references))),
            max_response_chars=max(500, int(cfg.get("max_response_chars", defaults.max_response_chars))),
            max_paragraphs=max(1, int(cfg.get("max_paragraphs", defaults.max_paragraphs))),
            export_best_consensus=bool(cfg.get("export_best_consensus", defaults.export_best_consensus)),
            persist_state=bool(cfg.get("persist_state", defaults.persist_state)),
        )
    except Exception:
        return defaults


def _collect_chat_references(topic: str, min_references: int) -> list[dict[str, Any]]:
    refs = _collect_references(topic)
    if len(refs) >= min_references:
        return refs[:min_references]

    extra_topics = [
        f"{topic} survey",
        f"{topic} benchmark",
        "multimodal large language model evaluation reliability",
    ]
    pool = list(refs)
    seen = {_title_key(r) for r in pool}
    for q in extra_topics:
        extra = _collect_references(q)
        for ref in extra:
            k = _title_key(ref)
            if not k or k in seen:
                continue
            seen.add(k)
            pool.append(ref)
        if len(pool) >= min_references:
            break

    pool.sort(key=lambda x: (int(x.get("year", 0) or 0), int(x.get("citation_count", 0) or 0)), reverse=True)
    if len(pool) < min_references:
        raise RuntimeError(
            f"Unable to retrieve at least {min_references} references with abstracts. "
            "Please broaden the topic or configure more sources."
        )
    return pool[:min_references]


def _title_key(ref: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(ref.get("title", "")).strip()).lower()


def _chat_generate(
    client: LLMClient,
    model: str,
    role_prompt_path: str,
    user_prompt: str,
    max_chars: int,
    max_paragraphs: int,
) -> str:
    system_prompt = Path(role_prompt_path).read_text(encoding="utf-8")
    text = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.45)
    text = _trim_to_char_limit(text, max_chars)
    return _trim_to_paragraph_limit(text, max_paragraphs)


def _trim_to_char_limit(text: str, max_chars: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 16].rstrip() + "\n\n[内容已截断]"


def _trim_to_paragraph_limit(text: str, max_paragraphs: int) -> str:
    if max_paragraphs <= 0:
        return text.strip()
    blocks = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(blocks) <= max_paragraphs:
        return "\n\n".join(blocks)
    kept = blocks[:max_paragraphs]
    tail = kept[-1]
    if "[内容已截断]" not in tail:
        kept[-1] = tail.rstrip() + "\n\n[段落已截断]"
    return "\n\n".join(kept)


def _build_reference_brief(refs: list[dict[str, Any]], max_items: int) -> str:
    lines: list[str] = []
    for i, ref in enumerate(refs[:max_items], start=1):
        title = str(ref.get("title", "")).strip()
        year = int(ref.get("year", 0) or 0)
        cites = int(ref.get("citation_count", 0) or 0)
        source = str(ref.get("source", ""))
        abstract = re.sub(r"\s+", " ", str(ref.get("abstract", "")).strip())
        if len(abstract) > 180:
            abstract = abstract[:177] + "..."
        lines.append(
            f"[{i}] ({source}, {year}, cites={cites}) {title} | 摘要: {abstract}"
        )
    return "\n".join(lines) if lines else "无可用参考文献"


def _extract_summary_anchor(moderator_output: str) -> str:
    text = re.sub(r"\s+", " ", moderator_output).strip()
    if len(text) <= 220:
        return text
    return text[:220] + "..."


def _parse_judge_decision(moderator_output: str) -> str:
    m = re.search(r"\[JUDGE_DECISION\]\s*:\s*([A-Z_]+)", moderator_output)
    if m:
        return m.group(1).strip().upper()
    text = moderator_output.lower()
    if "收敛" in text or "足够优秀" in text or "可停止" in text:
        return "STOP_CONVERGED"
    return "CONTINUE"


def _write_round_artifacts(chat_dir: Path, record: dict[str, Any]) -> None:
    rid = int(record["round_id"])
    proposer_file = chat_dir / f"round_{rid:02d}_proposer.md"
    skeptic_file = chat_dir / f"round_{rid:02d}_skeptic.md"
    moderator_file = chat_dir / f"round_{rid:02d}_moderator.md"
    combined_file = chat_dir / f"round_{rid:02d}.md"

    proposer_file.write_text(record["proposer"].strip() + "\n", encoding="utf-8")
    skeptic_file.write_text(record["skeptic"].strip() + "\n", encoding="utf-8")
    moderator_file.write_text(record["moderator"].strip() + "\n", encoding="utf-8")

    combined_file.write_text(
        "\n\n".join(
            [
                f"# Round {rid}",
                f"## Proposer\n{record['proposer'].strip()}",
                f"## Skeptic\n{record['skeptic'].strip()}",
                f"## Moderator\n{record['moderator'].strip()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _build_transcript(topic: str, rounds: list[dict[str, Any]]) -> str:
    lines = [
        "# CHAT_TRANSCRIPT",
        "",
        f"主题: {topic}",
        "",
    ]
    for item in rounds:
        rid = int(item["round_id"])
        lines.extend(
            [
                f"## Round {rid}",
                "",
                f"### Proposer\n{item['proposer']}",
                "",
                f"### Skeptic\n{item['skeptic']}",
                "",
                f"### Moderator\n{item['moderator']}",
                "",
                f"Decision: {item.get('judge_decision', 'CONTINUE')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _build_index(
    run_dir: Path,
    cfg: ChatModeConfig,
    reference_count: int,
    rounds: list[dict[str, Any]],
    stop_reason: str,
    consensus_file: Path | None,
) -> str:
    lines = [
        "# CHAT_MODE_INDEX",
        "",
        "本次为聊天式头脑风暴模式，不要求形式化证明，但保留文献支撑。",
        "",
        f"- min_rounds_before_stop: {cfg.min_rounds_before_stop}",
        f"- max_rounds: {'unlimited (judge decides)' if cfg.max_rounds == 0 else cfg.max_rounds}",
        f"- min_references: {cfg.min_references}",
        f"- max_response_chars_per_agent: {cfg.max_response_chars}",
        f"- max_paragraphs_per_agent: {cfg.max_paragraphs}",
        f"- retrieved_references: {reference_count}",
        f"- stop_reason: {stop_reason}",
        "",
        "| file | purpose |",
        "|---|---|",
        "| TOPIC_CHAT.txt | 输入主题 |",
        "| REFERENCES.md | 文献列表（含摘要） |",
        "| CHAT_TRANSCRIPT.md | 全量对话汇总 |",
        "| BEST_CONSENSUS.md | 最优共识方案（精简版） |",
        "| chat_mode_state.json | 结构化状态 |",
        "| chat_rounds/round_xx_proposer.md | 每轮正方发言 |",
        "| chat_rounds/round_xx_skeptic.md | 每轮反方发言 |",
        "| chat_rounds/round_xx_moderator.md | 每轮裁判发言 |",
        "| chat_rounds/round_xx.md | 每轮整合记录 |",
        "",
        f"本次完成轮数: {len(rounds)}",
    ]
    if consensus_file is None:
        lines.append("共识导出: disabled")
    if not (run_dir / "REFERENCES.md").exists():
        lines.append("\n警告: REFERENCES.md 未生成。")
    return "\n".join(lines).rstrip() + "\n"


def _export_best_consensus(
    client: LLMClient,
    model: str,
    topic: str,
    rounds: list[dict[str, Any]],
    refs: list[dict[str, Any]],
    output_file: Path,
    max_chars: int,
    max_paragraphs: int,
) -> Path:
    digest_lines: list[str] = []
    for item in rounds:
        digest_lines.append(
            f"R{item['round_id']} | P: {_extract_summary_anchor(str(item.get('proposer', '')))} | "
            f"S: {_extract_summary_anchor(str(item.get('skeptic', '')))} | "
            f"M: {_extract_summary_anchor(str(item.get('moderator', '')))} | "
            f"D: {item.get('judge_decision', 'CONTINUE')}"
        )
    reference_brief = _build_reference_brief(refs, max_items=min(20, len(refs)))

    system_prompt = (
        "你是研究负责人。基于完整辩论提炼一个可执行、可验证、可落地的最优共识方案。"
        "必须使用中文，强调创新性与可行性。"
    )
    user_prompt = (
        f"主题: {topic}\n\n"
        "请输出精简版共识方案，要求：\n"
        "1) 不超过3段，表达尽量精炼。\n"
        "2) 明确最终主方案、关键风险、最先执行的3步。\n"
        "3) 每个核心判断都要能被下列文献线索支撑（可用[1][2]这种引用标记）。\n"
        "4) 避免形式化证明和冗长铺垫。\n\n"
        f"文献索引:\n{reference_brief}\n\n"
        f"辩论摘要:\n{chr(10).join(digest_lines)}"
    )
    text = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.35)
    text = _trim_to_char_limit(text, max_chars)
    text = _trim_to_paragraph_limit(text, max_paragraphs)
    content = "# BEST_CONSENSUS\n\n" + text.strip() + "\n"
    output_file.write_text(content, encoding="utf-8")
    return output_file
