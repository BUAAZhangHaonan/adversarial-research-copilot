from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from arc.llm_client import LLMClient
from arc.run_paths import resolve_run_dir
from arc.runners.pipeline_runner import _collect_references, _format_references


@dataclass
class ChatModeConfig:
    rounds: int = 3
    min_references: int = 20
    max_response_chars: int = 1600
    persist_state: bool = True


def run_chat_mode(
    topic: str,
    proposer_model: str,
    skeptic_model: str,
    moderator_model: str,
    output_dir: str = "reports",
    resume: bool = False,
    run_dir: str | None = None,
) -> tuple[Path, Path]:
    cfg = _load_chat_mode_config()
    target_run_dir = Path(run_dir) if run_dir else resolve_run_dir(output_dir, resume, "chat_mode_state.json")
    target_run_dir.mkdir(parents=True, exist_ok=True)
    chat_dir = target_run_dir / "chat_rounds"
    chat_dir.mkdir(parents=True, exist_ok=True)

    client = LLMClient()
    refs = _collect_chat_references(topic, cfg.min_references)
    references_text = _format_references(refs)

    (target_run_dir / "TOPIC_CHAT.txt").write_text(topic.strip() + "\n", encoding="utf-8")
    (target_run_dir / "REFERENCES.md").write_text(references_text, encoding="utf-8")

    rounds: list[dict[str, Any]] = []
    prior_summary = ""
    reference_brief = _build_reference_brief(refs, max_items=cfg.min_references)

    for round_id in range(1, cfg.rounds + 1):
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
        )

        round_record = {
            "round_id": round_id,
            "proposer": proposer_output,
            "skeptic": skeptic_output,
            "moderator": moderator_output,
        }
        rounds.append(round_record)
        prior_summary = _extract_summary_anchor(moderator_output)

        _write_round_artifacts(chat_dir, round_record)

    transcript = _build_transcript(topic, rounds)
    transcript_file = target_run_dir / "CHAT_TRANSCRIPT.md"
    transcript_file.write_text(transcript, encoding="utf-8")

    index_file = target_run_dir / "CHAT_MODE_INDEX.md"
    index_file.write_text(
        _build_index(target_run_dir, cfg, len(refs), rounds),
        encoding="utf-8",
    )

    state_file = target_run_dir / "chat_mode_state.json"
    if cfg.persist_state:
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
                    "reference_count": len(refs),
                    "status": "completed",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return transcript_file, state_file


def _load_chat_mode_config(config_path: str | Path = "configs/chat_mode.yaml") -> ChatModeConfig:
    defaults = ChatModeConfig()
    p = Path(config_path)
    if not p.exists():
        return defaults
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        cfg = data.get("chat_mode", {}) if isinstance(data, dict) else {}
        return ChatModeConfig(
            rounds=max(1, int(cfg.get("rounds", defaults.rounds))),
            min_references=max(20, int(cfg.get("min_references", defaults.min_references))),
            max_response_chars=max(500, int(cfg.get("max_response_chars", defaults.max_response_chars))),
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
) -> str:
    system_prompt = Path(role_prompt_path).read_text(encoding="utf-8")
    text = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.45)
    return _trim_to_char_limit(text, max_chars)


def _trim_to_char_limit(text: str, max_chars: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 16].rstrip() + "\n\n[内容已截断]"


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
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _build_index(run_dir: Path, cfg: ChatModeConfig, reference_count: int, rounds: list[dict[str, Any]]) -> str:
    lines = [
        "# CHAT_MODE_INDEX",
        "",
        "本次为聊天式头脑风暴模式，不要求形式化证明，但保留文献支撑。",
        "",
        f"- rounds: {cfg.rounds}",
        f"- min_references: {cfg.min_references}",
        f"- max_response_chars_per_agent: {cfg.max_response_chars}",
        f"- retrieved_references: {reference_count}",
        "",
        "| file | purpose |",
        "|---|---|",
        "| TOPIC_CHAT.txt | 输入主题 |",
        "| REFERENCES.md | 文献列表（含摘要） |",
        "| CHAT_TRANSCRIPT.md | 全量对话汇总 |",
        "| chat_mode_state.json | 结构化状态 |",
        "| chat_rounds/round_xx_proposer.md | 每轮正方发言 |",
        "| chat_rounds/round_xx_skeptic.md | 每轮反方发言 |",
        "| chat_rounds/round_xx_moderator.md | 每轮裁判发言 |",
        "| chat_rounds/round_xx.md | 每轮整合记录 |",
        "",
        f"本次完成轮数: {len(rounds)}",
    ]
    if not (run_dir / "REFERENCES.md").exists():
        lines.append("\n警告: REFERENCES.md 未生成。")
    return "\n".join(lines).rstrip() + "\n"