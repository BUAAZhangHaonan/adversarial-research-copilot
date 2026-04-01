from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from arc.llm_client import LLMClient
from arc.prompting import localized_text, normalize_prompt_language, resolve_prompt_path
from arc.run_paths import ensure_run_dir_within_reports, resolve_run_dir
from arc.runners.pipeline_runner import _collect_references, _format_references


@dataclass
class ChatModeConfig:
    min_rounds_before_stop: int = 20
    # Advisory round target for planning and monitoring. Does not force stop.
    max_rounds: int = 60
    min_references: int = 20
    # Suggested response-size hint only, no hard truncation.
    max_response_chars: int = 3200
    # Suggested paragraph count only, no hard truncation.
    max_paragraphs: int = 3
    export_best_consensus: bool = True
    persist_state: bool = True
    prompt_language: str = "en"


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
    prompt_language: str | None = None,
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
    if prompt_language is not None:
        cfg.prompt_language = normalize_prompt_language(prompt_language)
    else:
        cfg.prompt_language = normalize_prompt_language(cfg.prompt_language)

    target_run_dir = (
        ensure_run_dir_within_reports(Path(run_dir), output_dir)
        if run_dir
        else resolve_run_dir(output_dir, resume, "chat_mode_state.json")
    )
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
    _backfill_round_timestamps(
        rounds=rounds,
        chat_dir=chat_dir,
        min_rounds_before_stop=cfg.min_rounds_before_stop,
        fallback_timestamp=str((resume_state or {}).get("timestamp", datetime.now(UTC).isoformat())),
    )
    prior_summary = _extract_summary_anchor(str(rounds[-1].get("moderator", ""))) if rounds else ""
    stop_reason = "running"
    reference_brief = _build_reference_brief(refs, max_items=cfg.min_references, language=cfg.prompt_language)
    start_round = max((int(item.get("round_id", 0)) for item in rounds), default=0) + 1

    if rounds:
        _write_interim_outputs(target_run_dir, topic, cfg, refs, rounds, stop_reason)
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
                status="in_progress",
            )

    round_id = start_round
    while True:
        round_started_at = datetime.now(UTC).isoformat()
        proposer_prompt_path = str(resolve_prompt_path("chat", "proposer_chat", cfg.prompt_language))
        proposer_output = _chat_generate(
            client=client,
            model=proposer_model,
            role_prompt_path=proposer_prompt_path,
            user_prompt=_build_proposer_user_prompt(
                round_id=round_id,
                topic=topic,
                reference_brief=reference_brief,
                prior_summary=prior_summary,
                min_references=cfg.min_references,
                language=cfg.prompt_language,
            ),
            max_chars=cfg.max_response_chars,
            max_paragraphs=cfg.max_paragraphs,
            language=cfg.prompt_language,
        )
        proposer_completed_at = datetime.now(UTC).isoformat()

        skeptic_prompt_path = str(resolve_prompt_path("chat", "skeptic_chat", cfg.prompt_language))
        skeptic_output = _chat_generate(
            client=client,
            model=skeptic_model,
            role_prompt_path=skeptic_prompt_path,
            user_prompt=_build_skeptic_user_prompt(
                round_id=round_id,
                topic=topic,
                reference_brief=reference_brief,
                proposer_output=proposer_output,
                min_references=cfg.min_references,
                language=cfg.prompt_language,
            ),
            max_chars=cfg.max_response_chars,
            max_paragraphs=cfg.max_paragraphs,
            language=cfg.prompt_language,
        )
        skeptic_completed_at = datetime.now(UTC).isoformat()

        moderator_prompt_path = str(resolve_prompt_path("chat", "moderator_chat", cfg.prompt_language))
        moderator_output = _chat_generate(
            client=client,
            model=moderator_model,
            role_prompt_path=moderator_prompt_path,
            user_prompt=_build_moderator_user_prompt(
                round_id=round_id,
                topic=topic,
                proposer_output=proposer_output,
                skeptic_output=skeptic_output,
                language=cfg.prompt_language,
            ),
            max_chars=cfg.max_response_chars,
            max_paragraphs=cfg.max_paragraphs,
            language=cfg.prompt_language,
        )
        moderator_completed_at = datetime.now(UTC).isoformat()

        raw_decision = _parse_judge_decision(moderator_output)
        effective_decision = raw_decision
        if raw_decision.startswith("STOP") and round_id < cfg.min_rounds_before_stop:
            effective_decision = "CONTINUE_MIN_ROUNDS_NOT_MET"

        round_completed_at = datetime.now(UTC).isoformat()
        round_record = {
            "round_id": round_id,
            "round_started_at": round_started_at,
            "proposer_completed_at": proposer_completed_at,
            "skeptic_completed_at": skeptic_completed_at,
            "moderator_completed_at": moderator_completed_at,
            "round_completed_at": round_completed_at,
            "reply_timestamps": {
                "proposer": proposer_completed_at,
                "skeptic": skeptic_completed_at,
                "moderator": moderator_completed_at,
            },
            "proposer": proposer_output,
            "skeptic": skeptic_output,
            "moderator": moderator_output,
            "judge_decision": effective_decision,
            "judge_decision_raw": raw_decision,
            "judge_decision_effective": effective_decision,
        }
        rounds.append(round_record)
        prior_summary = _extract_summary_anchor(moderator_output)

        _write_round_artifacts(chat_dir, round_record)
        _write_interim_outputs(target_run_dir, topic, cfg, refs, rounds, stop_reason)
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

        if round_id >= cfg.min_rounds_before_stop and effective_decision.startswith("STOP"):
            stop_reason = effective_decision
            break

        if cfg.max_rounds > 0 and round_id >= cfg.max_rounds:
            if effective_decision == "CONTINUE_NO_TAG":
                stop_reason = f"soft_target_reached_missing_judge_tag_{round_id}"
                break
            if effective_decision == "CONTINUE":
                stop_reason = f"soft_target_reached_continue_from_round_{round_id}"

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
            language=cfg.prompt_language,
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
                    "prompt_language": cfg.prompt_language,
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
            prompt_language=normalize_prompt_language(str(cfg.get("prompt_language", defaults.prompt_language))),
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


def _build_proposer_user_prompt(
    round_id: int,
    topic: str,
    reference_brief: str,
    prior_summary: str,
    min_references: int,
    language: str,
) -> str:
    return localized_text(
        language,
        (
            f"Round {round_id}.\n\n"
            f"Research topic: {topic}\n\n"
            f"Reference digest index (at least {min_references}):\n{reference_brief}\n\n"
            f"Latest moderator summary: {prior_summary or 'none'}\n\n"
            "Respond in English. Suggested length: 280-450 words (about 2-4 paragraphs).\n"
            "Do not self-truncate; keep full reasoning concise.\n"
            "Provide one strongest and executable path in chat style. Address unresolved tensions before introducing new claims."
        ),
        (
            f"第 {round_id} 轮。\n\n"
            f"研究主题: {topic}\n\n"
            f"参考文献摘要索引(至少{min_references}篇):\n{reference_brief}\n\n"
            f"上一轮裁判总结: {prior_summary or '无'}\n\n"
            "请以聊天风格给出唯一最强且可执行的方案路径，先回应未解争点，再推进新主张。"
        ),
    )


def _build_skeptic_user_prompt(
    round_id: int,
    topic: str,
    reference_brief: str,
    proposer_output: str,
    min_references: int,
    language: str,
) -> str:
    return localized_text(
        language,
        (
            f"Round {round_id}.\n\n"
            f"Research topic: {topic}\n\n"
            f"Reference digest index (at least {min_references}):\n{reference_brief}\n\n"
            f"Proposer view:\n{proposer_output}\n\n"
            "Respond in English. Suggested length: 280-450 words (about 2-4 paragraphs).\n"
            "Do not self-truncate; keep full reasoning concise.\n"
            "Pressure-test with concrete failure scenarios, boundary conditions, and minimum evidence needed to unblock decisions."
        ),
        (
            f"第 {round_id} 轮。\n\n"
            f"研究主题: {topic}\n\n"
            f"参考文献摘要索引(至少{min_references}篇):\n{reference_brief}\n\n"
            f"正方观点:\n{proposer_output}\n\n"
            "请给出具体失败场景、边界条件与最小补证动作，优先指出真正影响决策的关键风险。"
        ),
    )


def _build_moderator_user_prompt(
    round_id: int,
    topic: str,
    proposer_output: str,
    skeptic_output: str,
    language: str,
) -> str:
    return localized_text(
        language,
        (
            f"Round {round_id}.\n\n"
            f"Research topic: {topic}\n\n"
            f"Proposer:\n{proposer_output}\n\n"
            f"Skeptic:\n{skeptic_output}\n\n"
            "Respond in English. Suggested length: 240-420 words (about 2-4 paragraphs).\n"
            "Do not self-truncate; ensure the final line contains an exact [JUDGE_DECISION] tag.\n"
            "Issue a convergence-focused ruling with one decisive next focus, then end with the exact [JUDGE_DECISION] marker."
        ),
        (
            f"第 {round_id} 轮。\n\n"
            f"研究主题: {topic}\n\n"
            f"正方:\n{proposer_output}\n\n"
            f"反方:\n{skeptic_output}\n\n"
            "请给出收敛导向裁决、唯一关键下一轮焦点，并在最后一行输出精确的 [JUDGE_DECISION] 标记。"
        ),
    )


def _chat_generate(
    client: LLMClient,
    model: str,
    role_prompt_path: str,
    user_prompt: str,
    max_chars: int,
    max_paragraphs: int,
    language: str,
) -> str:
    system_prompt = Path(role_prompt_path).read_text(encoding="utf-8")
    text = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.45)
    return text.strip()


def _trim_to_char_limit(text: str, max_chars: int, language: str) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    marker = localized_text(language, "[content truncated]", "[内容已截断]")
    safe_limit = max(1, max_chars - len(marker) - 2)
    return cleaned[:safe_limit].rstrip() + "\n\n" + marker


def _trim_to_paragraph_limit(text: str, max_paragraphs: int, language: str) -> str:
    if max_paragraphs <= 0:
        return text.strip()
    blocks = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(blocks) <= max_paragraphs:
        return "\n\n".join(blocks)
    kept = blocks[:max_paragraphs]
    tail = kept[-1]
    marker = localized_text(language, "[paragraphs truncated]", "[段落已截断]")
    if marker not in tail:
        kept[-1] = tail.rstrip() + "\n\n" + marker
    return "\n\n".join(kept)


def _build_reference_brief(refs: list[dict[str, Any]], max_items: int, language: str) -> str:
    lines: list[str] = []
    for i, ref in enumerate(refs[:max_items], start=1):
        title = str(ref.get("title", "")).strip()
        year = int(ref.get("year", 0) or 0)
        cites = int(ref.get("citation_count", 0) or 0)
        source = str(ref.get("source", ""))
        abstract = re.sub(r"\s+", " ", str(ref.get("abstract", "")).strip())
        if len(abstract) > 180:
            abstract = abstract[:177] + "..."
        if normalize_prompt_language(language) == "zh":
            lines.append(f"[{i}] ({source}, {year}, cites={cites}) {title} | 摘要: {abstract}")
        else:
            lines.append(f"[{i}] ({source}, {year}, cites={cites}) {title} | abstract: {abstract}")
    return "\n".join(lines) if lines else localized_text(language, "No references available", "无可用参考文献")


def _extract_summary_anchor(moderator_output: str) -> str:
    text = re.sub(r"\s+", " ", moderator_output).strip()
    if len(text) <= 220:
        return text
    return text[:220] + "..."


def _parse_judge_decision(moderator_output: str) -> str:
    m = re.search(r"\[JUDGE_DECISION\]\s*:\s*([A-Z_]+)", moderator_output, flags=re.IGNORECASE)
    if m:
        decision = m.group(1).strip().upper()
        allowed = {"CONTINUE", "STOP_CONVERGED", "STOP_PROPOSER_SUFFICIENT"}
        return decision if decision in allowed else "CONTINUE_NO_TAG"
    text_upper = moderator_output.upper()
    if re.search(r"\bSTOP_CONVERGED\b", text_upper):
        return "STOP_CONVERGED"
    if re.search(r"\bSTOP_PROPOSER_SUFFICIENT\b", text_upper):
        return "STOP_PROPOSER_SUFFICIENT"
    if re.search(r"\bCONTINUE\b", text_upper):
        return "CONTINUE"
    return "CONTINUE_NO_TAG"


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
                f"time: {record.get('round_started_at', '')} -> {record.get('round_completed_at', '')}",
                f"decision(raw/effective): {record.get('judge_decision_raw', record.get('judge_decision', ''))} / {record.get('judge_decision_effective', record.get('judge_decision', ''))}",
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
        f"topic: {topic}",
        "",
    ]
    for item in rounds:
        rid = int(item["round_id"])
        lines.extend(
            [
                f"## Round {rid}",
                "",
                f"time: {item.get('round_started_at', '')} -> {item.get('round_completed_at', '')}",
                f"decision(raw/effective): {item.get('judge_decision_raw', item.get('judge_decision', ''))} / {item.get('judge_decision_effective', item.get('judge_decision', ''))}",
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


def _backfill_round_timestamps(
    rounds: list[dict[str, Any]],
    chat_dir: Path,
    min_rounds_before_stop: int,
    fallback_timestamp: str,
) -> None:
    if not rounds:
        return
    for item in rounds:
        rid = int(item.get("round_id", 0) or 0)
        round_file = chat_dir / f"round_{rid:02d}.md"
        ts = fallback_timestamp
        try:
            if round_file.exists():
                ts = datetime.fromtimestamp(round_file.stat().st_mtime, tz=UTC).isoformat()
        except Exception:
            ts = fallback_timestamp

        item.setdefault("round_started_at", ts)
        item.setdefault("proposer_completed_at", ts)
        item.setdefault("skeptic_completed_at", ts)
        item.setdefault("moderator_completed_at", ts)
        item.setdefault("round_completed_at", ts)
        item.setdefault(
            "reply_timestamps",
            {
                "proposer": item.get("proposer_completed_at", ts),
                "skeptic": item.get("skeptic_completed_at", ts),
                "moderator": item.get("moderator_completed_at", ts),
            },
        )

        raw = str(item.get("judge_decision_raw", item.get("judge_decision", "CONTINUE"))).strip() or "CONTINUE"
        eff = str(item.get("judge_decision_effective", item.get("judge_decision", raw))).strip() or raw
        if raw.startswith("STOP") and rid < min_rounds_before_stop:
            eff = "CONTINUE_MIN_ROUNDS_NOT_MET"
        item["judge_decision_raw"] = raw
        item["judge_decision_effective"] = eff
        item["judge_decision"] = eff


def _write_interim_outputs(
    run_dir: Path,
    topic: str,
    cfg: ChatModeConfig,
    refs: list[dict[str, Any]],
    rounds: list[dict[str, Any]],
    stop_reason: str,
) -> None:
    transcript_file = run_dir / "CHAT_TRANSCRIPT.md"
    transcript_file.write_text(_build_transcript(topic, rounds), encoding="utf-8")

    consensus_file = run_dir / "BEST_CONSENSUS.md"
    _write_interim_consensus(topic=topic, rounds=rounds, output_file=consensus_file)

    index_file = run_dir / "CHAT_MODE_INDEX.md"
    index_file.write_text(
        _build_index(run_dir, cfg, len(refs), rounds, stop_reason, consensus_file),
        encoding="utf-8",
    )


def _write_interim_consensus(topic: str, rounds: list[dict[str, Any]], output_file: Path) -> None:
    if not rounds:
        return
    last = rounds[-1]
    content = [
        "# BEST_CONSENSUS",
        "",
        "_INTERIM DRAFT: generated during running process; final version will be refined at completion._",
        "",
        f"topic: {topic}",
        f"latest_round: {last.get('round_id')}",
        f"decision(raw/effective): {last.get('judge_decision_raw', last.get('judge_decision'))} / {last.get('judge_decision_effective', last.get('judge_decision'))}",
        f"timestamp: {last.get('round_completed_at', '')}",
        "",
        "## Latest Moderator Summary",
        "",
        str(last.get("moderator", "")).strip(),
        "",
    ]
    output_file.write_text("\n".join(content), encoding="utf-8")


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
        "This run uses chat-mode brainstorming with evidence grounding and non-forced length guidance.",
        "",
        f"- min_rounds_before_stop: {cfg.min_rounds_before_stop}",
        f"- max_rounds_soft_target: {'disabled' if cfg.max_rounds == 0 else cfg.max_rounds}",
        f"- min_references: {cfg.min_references}",
        f"- suggested_max_response_chars_per_agent: {cfg.max_response_chars}",
        f"- suggested_max_paragraphs_per_agent: {cfg.max_paragraphs}",
        f"- prompt_language: {cfg.prompt_language}",
        f"- retrieved_references: {reference_count}",
        f"- stop_reason: {stop_reason}",
        "",
        "| file | purpose |",
        "|---|---|",
        "| TOPIC_CHAT.txt | Topic input |",
        "| REFERENCES.md | Reference list with abstracts |",
        "| CHAT_TRANSCRIPT.md | Full conversation transcript |",
        "| BEST_CONSENSUS.md | Condensed best consensus |",
        "| chat_mode_state.json | Structured state with timestamps |",
        "| chat_rounds/round_xx_proposer.md | Proposer per-round message |",
        "| chat_rounds/round_xx_skeptic.md | Skeptic per-round message |",
        "| chat_rounds/round_xx_moderator.md | Moderator per-round message |",
        "| chat_rounds/round_xx.md | Combined per-round log |",
        "",
        f"completed_rounds: {len(rounds)}",
    ]
    if consensus_file is None:
        lines.append("consensus_export: disabled")
    if not (run_dir / "REFERENCES.md").exists():
        lines.append("\nwarning: REFERENCES.md was not generated.")
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
    language: str,
) -> Path:
    digest_lines: list[str] = []
    for item in rounds:
        digest_lines.append(
            f"R{item['round_id']} | P: {_extract_summary_anchor(str(item.get('proposer', '')))} | "
            f"S: {_extract_summary_anchor(str(item.get('skeptic', '')))} | "
            f"M: {_extract_summary_anchor(str(item.get('moderator', '')))} | "
            f"D: {item.get('judge_decision', 'CONTINUE')}"
        )
    reference_brief = _build_reference_brief(refs, max_items=min(20, len(refs)), language=language)

    system_prompt = localized_text(
        language,
        (
            "You are the research lead. Distill the debate into one executable and falsifiable consensus plan. "
            "Keep it concise, evidence-bound, and decision-oriented."
        ),
        (
            "你是研究负责人。基于完整辩论提炼一个可执行、可验证、可落地的最优共识方案。"
            "保持精炼、证据绑定与决策导向。"
        ),
    )
    user_prompt = localized_text(
        language,
        (
            f"Topic: {topic}\n\n"
            "Output a concise consensus with requirements:\n"
            "1) No more than 3 paragraphs.\n"
            "2) State final primary path, key risk, and first 3 execution steps.\n"
            "3) Anchor core claims to references using citation tags like [1][2].\n"
            "4) Avoid formal-proof style and long preambles.\n\n"
            f"Reference index:\n{reference_brief}\n\n"
            f"Debate digest:\n{chr(10).join(digest_lines)}"
        ),
        (
            f"主题: {topic}\n\n"
            "请输出精简版共识方案，要求：\n"
            "1) 不超过3段，表达尽量精炼。\n"
            "2) 明确最终主方案、关键风险、最先执行的3步。\n"
            "3) 每个核心判断都要能被文献线索支撑（可用[1][2]引用标记）。\n"
            "4) 避免形式化证明和冗长铺垫。\n\n"
            f"文献索引:\n{reference_brief}\n\n"
            f"辩论摘要:\n{chr(10).join(digest_lines)}"
        ),
    )
    text = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.35)
    content = "# BEST_CONSENSUS\n\n" + text.strip() + "\n"
    output_file.write_text(content, encoding="utf-8")
    return output_file
