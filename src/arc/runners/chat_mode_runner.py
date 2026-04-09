from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from arc.agents.drift_monitor import DriftMonitorAgent
from arc.agents.reviewer import ReviewerAgent, parse_reviewer_decision
from arc.llm_client import LLMClient
from arc.prompting import localized_text, normalize_prompt_language, resolve_prompt_path
from arc.providers.literature import collect_references_deepxiv_primary
from arc.run_paths import ensure_run_dir_within_reports, resolve_run_dir, sanitize_model_suffix
from arc.skill_engine import load_skills_dir

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

CHAT_PIPELINE_STAGES = [
    "literature-research",
    "idea-creation",
    "novelty-check",
    "evidence-grounding",
    "research-refine",
    "experiment-bridge",
    "debate-rounds",
    "auto-review",
    "memo-synthesis",
]

# Maps stage name to the skill that provides its system prompt body.
_STAGE_SKILL_MAP: dict[str, str] = {
    "literature-research": "research-lit",
    "idea-creation": "idea-creator",
    "novelty-check": "novelty-check",
    "evidence-grounding": "evidence-grounding",
    "research-refine": "research-refine",
    "experiment-bridge": "experiment-bridge",
    "auto-review": "auto-review-loop",
    "memo-synthesis": "memo-synthesis",
}

# Maps stage name to which role's model to use.
_STAGE_MODEL_ROLE: dict[str, str] = {
    "literature-research": "proposer",
    "idea-creation": "proposer",
    "novelty-check": "skeptic",
    "evidence-grounding": "skeptic",
    "research-refine": "proposer",
    "experiment-bridge": "proposer",
    "debate-rounds": "moderator",  # special: uses all three
    "auto-review": "skeptic",
    "memo-synthesis": "moderator",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ChatModeConfig:
    min_rounds_before_stop: int = 20
    max_rounds: int = 60
    min_references: int = 20
    max_response_chars: int = 3200
    max_paragraphs: int = 3
    export_best_consensus: bool = True
    persist_state: bool = True
    prompt_language: str = "en"
    drift_check_interval: int = 5
    max_review_cycles: int = 99
    max_inner_debate_rounds: int = 99


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

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
    max_review_cycles: int | None = None,
    max_inner_debate_rounds: int | None = None,
    drift_check_interval: int | None = None,
) -> tuple[Path, Path]:
    """Run the full chat-mode pipeline (9 stages with nested review loops)."""
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
    if max_review_cycles is not None:
        cfg.max_review_cycles = max(0, int(max_review_cycles))
    if max_inner_debate_rounds is not None:
        cfg.max_inner_debate_rounds = max(0, int(max_inner_debate_rounds))
    if drift_check_interval is not None:
        cfg.drift_check_interval = max(1, int(drift_check_interval))

    models = {"proposer": proposer_model, "skeptic": skeptic_model, "moderator": moderator_model}
    msuffix = sanitize_model_suffix(proposer_model, skeptic_model, moderator_model)

    target_run_dir = (
        ensure_run_dir_within_reports(Path(run_dir), output_dir)
        if run_dir
        else resolve_run_dir(output_dir, resume, "chat_mode_state.json", model_suffix=msuffix)
    )
    state_file = target_run_dir / "chat_mode_state.json"

    # Resume handling
    resume_state, resumed = _load_chat_resume_state(
        target_run_dir, topic=topic, models=models, resume=resume, max_stale_hours=24,
    )
    if resume and run_dir is None and not resumed and state_file.exists():
        target_run_dir = resolve_run_dir(output_dir, False, "chat_mode_state.json", model_suffix=msuffix)
        state_file = target_run_dir / "chat_mode_state.json"
        resume_state, resumed = _load_chat_resume_state(
            target_run_dir, topic=topic, models=models, resume=False, max_stale_hours=24,
        )

    target_run_dir.mkdir(parents=True, exist_ok=True)
    chat_dir = target_run_dir / "chat_rounds"
    chat_dir.mkdir(parents=True, exist_ok=True)

    if resumed:
        existing_topic = (target_run_dir / "TOPIC_CHAT.txt").read_text(
            encoding="utf-8").strip() if (target_run_dir / "TOPIC_CHAT.txt").exists() else ""
        if existing_topic and existing_topic != topic.strip():
            raise RuntimeError(
                "Resume requested with a different topic than the in-progress chat run.")

    (target_run_dir / "TOPIC_CHAT.txt").write_text(topic.strip() + "\n", encoding="utf-8")

    client = LLMClient()
    skills = load_skills_dir("skills")

    # Determine which stages are already completed (for resume)
    stage_statuses: dict[str, str] = {}
    if resume_state and isinstance(resume_state.get("stage_statuses"), dict):
        stage_statuses = resume_state["stage_statuses"]

    # Restore debate state for resume
    rounds: list[dict[str, Any]] = list(resume_state.get("rounds", [])) if resume_state else []
    review_cycles_data: list[dict[str, Any]] = list(resume_state.get("review_cycles", [])) if resume_state else []
    debate_review_cycle = int((resume_state or {}).get("debate_review_cycle", 0))
    debate_inner_round = int((resume_state or {}).get("debate_inner_round", 0))
    prior_reviewer_feedback = str((resume_state or {}).get("prior_reviewer_feedback", ""))

    _backfill_round_timestamps(
        rounds=rounds, chat_dir=chat_dir,
        min_rounds_before_stop=cfg.min_rounds_before_stop,
        fallback_timestamp=str((resume_state or {}).get("timestamp", datetime.now(UTC).isoformat())),
    )

    stop_reason = "running"

    # ---------------------------------------------------------------
    # Execute pipeline stages 1-6 only (8-9 run after debate)
    # ---------------------------------------------------------------
    _PRE_DEBATE_STAGES = [s for s in CHAT_PIPELINE_STAGES if s not in ("debate-rounds", "auto-review", "memo-synthesis")]
    for stage_name in _PRE_DEBATE_STAGES:
        if stage_statuses.get(stage_name) == "completed":
            continue

        _run_pre_debate_stage(
            stage_name=stage_name,
            run_dir=target_run_dir,
            client=client,
            models=models,
            skills=skills,
            topic=topic,
            cfg=cfg,
        )
        stage_statuses[stage_name] = "completed"
        _save_state(
            state_file=state_file, topic=topic, rounds=rounds, models=models,
            cfg=cfg, reference_count=0, stop_reason=stop_reason, status="in_progress",
            stage_statuses=stage_statuses, review_cycles=review_cycles_data,
            debate_review_cycle=debate_review_cycle, debate_inner_round=debate_inner_round,
            prior_reviewer_feedback=prior_reviewer_feedback,
        )

    # ---------------------------------------------------------------
    # Stage 7: debate-rounds (nested loops with reviewer + drift monitor)
    # ---------------------------------------------------------------
    if stage_statuses.get("debate-rounds") != "completed":
        refs = _collect_chat_references(topic, cfg.min_references)
        references_text = _format_references(refs)
        (target_run_dir / "REFERENCES.md").write_text(references_text, encoding="utf-8")
        reference_brief = _build_reference_brief(refs, max_items=cfg.min_references, language=cfg.prompt_language)
        prior_summary = _extract_summary_anchor(str(rounds[-1].get("moderator", ""))) if rounds else ""
        start_inner = debate_inner_round + 1 if debate_inner_round > 0 else 1
        start_cycle = debate_review_cycle + 1 if debate_review_cycle > 0 else 1

        if rounds:
            _write_interim_outputs(target_run_dir, topic, cfg, refs, rounds, stop_reason)

        drift_monitor = DriftMonitorAgent(client, models["moderator"], cfg.prompt_language, mode="chat")
        reviewer = ReviewerAgent(client, models["skeptic"], cfg.prompt_language, mode="chat")

        for review_cycle_id in range(start_cycle, cfg.max_review_cycles + 1):
            # Inject reviewer feedback from previous cycle
            cycle_reviewer_feedback = prior_reviewer_feedback if review_cycle_id == start_cycle and prior_reviewer_feedback else ""
            cycle_start_round = start_inner if review_cycle_id == start_cycle else 1

            for inner_round in range(cycle_start_round, cfg.max_inner_debate_rounds + 1):
                global_round_id = len(rounds) + 1
                round_started_at = datetime.now(UTC).isoformat()

                # Drift monitor check
                drift_correction = ""
                if inner_round > 1 and inner_round % cfg.drift_check_interval == 0:
                    drift_out = drift_monitor.run(
                        original_topic=topic,
                        current_summary=prior_summary,
                        round_id=global_round_id,
                    )
                    drift_data = _parse_yaml_block(drift_out)
                    if drift_data.get("drift_detected") is True and drift_data.get("correction"):
                        drift_correction = str(drift_data["correction"])

                # Proposer
                proposer_prompt_path = str(resolve_prompt_path("chat", "proposer_chat", cfg.prompt_language))
                proposer_extra = ""
                if cycle_reviewer_feedback:
                    proposer_extra += f"\n[REVIEWER FEEDBACK FROM PREVIOUS CYCLE]\n{cycle_reviewer_feedback}\n"
                if drift_correction:
                    proposer_extra += f"\n[DRIFT CORRECTION]\n{drift_correction}\n"
                proposer_output = _chat_generate(
                    client=client, model=models["proposer"],
                    role_prompt_path=proposer_prompt_path,
                    user_prompt=_build_proposer_user_prompt(
                        round_id=global_round_id, topic=topic, reference_brief=reference_brief,
                        prior_summary=prior_summary, min_references=cfg.min_references,
                        language=cfg.prompt_language,
                    ) + proposer_extra,
                    max_chars=cfg.max_response_chars, max_paragraphs=cfg.max_paragraphs,
                    language=cfg.prompt_language,
                )
                proposer_completed_at = datetime.now(UTC).isoformat()

                # Skeptic
                skeptic_prompt_path = str(resolve_prompt_path("chat", "skeptic_chat", cfg.prompt_language))
                skeptic_output = _chat_generate(
                    client=client, model=models["skeptic"],
                    role_prompt_path=skeptic_prompt_path,
                    user_prompt=_build_skeptic_user_prompt(
                        round_id=global_round_id, topic=topic, reference_brief=reference_brief,
                        proposer_output=proposer_output, min_references=cfg.min_references,
                        language=cfg.prompt_language,
                    ),
                    max_chars=cfg.max_response_chars, max_paragraphs=cfg.max_paragraphs,
                    language=cfg.prompt_language,
                )
                skeptic_completed_at = datetime.now(UTC).isoformat()

                # Moderator
                moderator_prompt_path = str(resolve_prompt_path("chat", "moderator_chat", cfg.prompt_language))
                moderator_output = _chat_generate(
                    client=client, model=models["moderator"],
                    role_prompt_path=moderator_prompt_path,
                    user_prompt=_build_moderator_user_prompt(
                        round_id=global_round_id, topic=topic,
                        proposer_output=proposer_output, skeptic_output=skeptic_output,
                        language=cfg.prompt_language,
                    ),
                    max_chars=cfg.max_response_chars, max_paragraphs=cfg.max_paragraphs,
                    language=cfg.prompt_language,
                )
                moderator_completed_at = datetime.now(UTC).isoformat()

                raw_decision = _parse_judge_decision(moderator_output)
                effective_decision = raw_decision
                if raw_decision.startswith("STOP") and global_round_id < cfg.min_rounds_before_stop:
                    effective_decision = "CONTINUE_MIN_ROUNDS_NOT_MET"

                round_completed_at = datetime.now(UTC).isoformat()
                round_record = {
                    "round_id": global_round_id,
                    "review_cycle": review_cycle_id,
                    "inner_round": inner_round,
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

                debate_inner_round = inner_round
                debate_review_cycle = review_cycle_id
                _save_state(
                    state_file=state_file, topic=topic, rounds=rounds, models=models,
                    cfg=cfg, reference_count=len(refs), stop_reason=stop_reason, status="in_progress",
                    stage_statuses=stage_statuses, review_cycles=review_cycles_data,
                    debate_review_cycle=debate_review_cycle, debate_inner_round=debate_inner_round,
                    prior_reviewer_feedback=prior_reviewer_feedback,
                )

                # Inner loop stopping conditions
                if global_round_id >= cfg.min_rounds_before_stop and effective_decision.startswith("STOP"):
                    break

                if cfg.max_rounds > 0 and global_round_id >= cfg.max_rounds:
                    if effective_decision == "CONTINUE_NO_TAG":
                        stop_reason = f"soft_target_reached_missing_judge_tag_{global_round_id}"
                        break
                    if effective_decision == "CONTINUE":
                        stop_reason = f"soft_target_reached_continue_from_round_{global_round_id}"

            # --- Reviewer evaluation after inner loop convergence ---
            consensus_file = target_run_dir / "BEST_CONSENSUS.md"
            consensus_text = consensus_file.read_text(encoding="utf-8") if consensus_file.exists() else prior_summary

            reviewer_output = reviewer.run(
                consensus_document=consensus_text,
                topic=topic,
                review_cycle=review_cycle_id,
                prior_reviewer_feedback=cycle_reviewer_feedback,
            )
            review_decision = parse_reviewer_decision(reviewer_output)

            review_cycles_data.append({
                "review_cycle": review_cycle_id,
                "reviewer_output": reviewer_output,
                "review_decision": review_decision.get("review_decision", "UNRESOLVED"),
                "inner_rounds_completed": debate_inner_round,
            })

            if review_decision.get("review_decision") == "RESOLVED":
                stop_reason = f"reviewer_resolved_cycle_{review_cycle_id}"
                prior_reviewer_feedback = ""
                break

            # Unresolved: inject feedback for next cycle
            issues = review_decision.get("unresolved_issues", [])
            prior_reviewer_feedback = "\n".join(f"- {iss}" for iss in issues) if issues else reviewer_output[:500]
            debate_inner_round = 0  # reset inner round counter for next cycle
        else:
            stop_reason = f"max_review_cycles_reached_{cfg.max_review_cycles}"

        stage_statuses["debate-rounds"] = "completed"

    # ---------------------------------------------------------------
    # Stages 8-9: auto-review and memo-synthesis
    # ---------------------------------------------------------------
    for stage_name in ["auto-review", "memo-synthesis"]:
        if stage_statuses.get(stage_name) == "completed":
            continue
        _run_pre_debate_stage(
            stage_name=stage_name, run_dir=target_run_dir,
            client=client, models=models, skills=skills, topic=topic, cfg=cfg,
        )
        stage_statuses[stage_name] = "completed"

    # ---------------------------------------------------------------
    # Final outputs
    # ---------------------------------------------------------------
    refs = []
    if (target_run_dir / "REFERENCES.md").exists():
        refs = []  # references already saved to file

    transcript = _build_transcript(topic, rounds)
    transcript_file = target_run_dir / "CHAT_TRANSCRIPT.md"
    transcript_file.write_text(transcript, encoding="utf-8")

    consensus_file: Path | None = None
    if cfg.export_best_consensus:
        consensus_file = _export_best_consensus(
            client=client, model=models["moderator"], topic=topic, rounds=rounds,
            refs=[], output_file=target_run_dir / "BEST_CONSENSUS.md",
            max_chars=cfg.max_response_chars, max_paragraphs=cfg.max_paragraphs,
            language=cfg.prompt_language,
        )

    # Build review cycles report
    if review_cycles_data:
        _write_review_cycles_report(target_run_dir, review_cycles_data)

    index_file = target_run_dir / "CHAT_MODE_INDEX.md"
    index_file.write_text(
        _build_index(target_run_dir, cfg, len(refs), rounds, stop_reason, consensus_file, review_cycles_data),
        encoding="utf-8",
    )

    if cfg.persist_state:
        _save_state(
            state_file=state_file, topic=topic, rounds=rounds, models=models,
            cfg=cfg, reference_count=len(refs), stop_reason=stop_reason, status="completed",
            stage_statuses=stage_statuses, review_cycles=review_cycles_data,
            debate_review_cycle=debate_review_cycle, debate_inner_round=debate_inner_round,
            prior_reviewer_feedback=prior_reviewer_feedback,
        )

    return transcript_file, state_file


# ---------------------------------------------------------------------------
# Stage execution for stages 1-6, 8-9
# ---------------------------------------------------------------------------

def _run_pre_debate_stage(
    stage_name: str,
    run_dir: Path,
    client: LLMClient,
    models: dict[str, str],
    skills: dict,
    topic: str,
    cfg: ChatModeConfig,
) -> None:
    """Execute a single pipeline stage (stages 1-6, 8-9)."""
    skill_key = _STAGE_SKILL_MAP.get(stage_name)
    if not skill_key:
        return

    skill = skills.get(skill_key)
    system_prompt = skill.body_markdown if skill else f"You are a research assistant performing the {stage_name} stage."
    model = models.get(_STAGE_MODEL_ROLE.get(stage_name, "proposer"), models["proposer"])

    if stage_name == "literature-research":
        refs = _collect_chat_references(topic, cfg.min_references)
        references_text = _format_references(refs)
        (run_dir / "REFERENCES.md").write_text(references_text, encoding="utf-8")
        user_prompt = f"Research topic: {topic}\n\nReferences:\n{_build_reference_brief(refs, cfg.min_references, cfg.prompt_language)}\n\nGenerate a comprehensive literature map."
        output = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        (run_dir / "LITERATURE_MAP.md").write_text(output.strip() + "\n", encoding="utf-8")

    elif stage_name == "idea-creation":
        lit_map = (run_dir / "LITERATURE_MAP.md").read_text(encoding="utf-8") if (run_dir / "LITERATURE_MAP.md").exists() else ""
        user_prompt = f"Research topic: {topic}\n\nLiterature map:\n{lit_map}\n\nGenerate candidate research ideas."
        output = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        (run_dir / "IDEA_REPORT.md").write_text(output.strip() + "\n", encoding="utf-8")

    elif stage_name == "novelty-check":
        idea_report = (run_dir / "IDEA_REPORT.md").read_text(encoding="utf-8") if (run_dir / "IDEA_REPORT.md").exists() else ""
        refs_text = (run_dir / "REFERENCES.md").read_text(encoding="utf-8") if (run_dir / "REFERENCES.md").exists() else ""
        user_prompt = f"Research topic: {topic}\n\nIdea report:\n{idea_report}\n\nReferences:\n{refs_text}\n\nPerform a strict novelty check and produce a final proposal."
        output = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        (run_dir / "FINAL_PROPOSAL.md").write_text(output.strip() + "\n", encoding="utf-8")

    elif stage_name == "evidence-grounding":
        proposal = (run_dir / "FINAL_PROPOSAL.md").read_text(encoding="utf-8") if (run_dir / "FINAL_PROPOSAL.md").exists() else ""
        refs_text = (run_dir / "REFERENCES.md").read_text(encoding="utf-8") if (run_dir / "REFERENCES.md").exists() else ""
        user_prompt = f"Research topic: {topic}\n\nProposal:\n{proposal}\n\nReferences:\n{refs_text}\n\nCreate an evidence-grounding table."
        output = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        (run_dir / "EVIDENCE_TABLE.md").write_text(output.strip() + "\n", encoding="utf-8")

    elif stage_name == "research-refine":
        proposal = (run_dir / "FINAL_PROPOSAL.md").read_text(encoding="utf-8") if (run_dir / "FINAL_PROPOSAL.md").exists() else ""
        user_prompt = f"Research topic: {topic}\n\nCurrent proposal:\n{proposal}\n\nRefine for falsifiability and resource constraints."
        output = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        (run_dir / "FINAL_PROPOSAL.md").write_text(output.strip() + "\n", encoding="utf-8")

    elif stage_name == "experiment-bridge":
        proposal = (run_dir / "FINAL_PROPOSAL.md").read_text(encoding="utf-8") if (run_dir / "FINAL_PROPOSAL.md").exists() else ""
        user_prompt = f"Research topic: {topic}\n\nProposal:\n{proposal}\n\nGenerate an experiment plan."
        output = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        (run_dir / "EXPERIMENT_PLAN.md").write_text(output.strip() + "\n", encoding="utf-8")

    elif stage_name == "auto-review":
        memo = (run_dir / "RESEARCH_DECISION_MEMO.md").read_text(encoding="utf-8") if (run_dir / "RESEARCH_DECISION_MEMO.md").exists() else ""
        if not memo:
            # Fall back to BEST_CONSENSUS if no formal memo yet
            memo = (run_dir / "BEST_CONSENSUS.md").read_text(encoding="utf-8") if (run_dir / "BEST_CONSENSUS.md").exists() else ""
        if not memo:
            return
        user_prompt = f"Research topic: {topic}\n\nDocument to review:\n{memo}\n\nPerform an auto-review."
        output = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        (run_dir / "AUTO_REVIEW.md").write_text(output.strip() + "\n", encoding="utf-8")
        # Extract revised memo if present
        revised = _extract_revised_memo(output)
        if revised:
            (run_dir / "RESEARCH_DECISION_MEMO.md").write_text(revised.strip() + "\n", encoding="utf-8")

    elif stage_name == "memo-synthesis":
        memo_file = run_dir / "RESEARCH_DECISION_MEMO.md"
        existing = memo_file.read_text(encoding="utf-8").strip() if memo_file.exists() else ""
        # Overwrite placeholder memos with a real synthesis if BEST_CONSENSUS exists
        consensus = (run_dir / "BEST_CONSENSUS.md").read_text(encoding="utf-8").strip() if (run_dir / "BEST_CONSENSUS.md").exists() else ""
        if consensus and (not existing or "pending" in existing.lower()):
            memo_file.write_text(consensus + "\n", encoding="utf-8")
        elif not existing:
            memo_file.write_text(f"# Research Decision Memo\n\nTopic: {topic}\n\nMemo synthesis pending.\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _save_state(
    state_file: Path,
    topic: str,
    rounds: list[dict[str, Any]],
    models: dict[str, str],
    cfg: ChatModeConfig,
    reference_count: int,
    stop_reason: str,
    status: str,
    stage_statuses: dict[str, str] | None = None,
    review_cycles: list[dict[str, Any]] | None = None,
    debate_review_cycle: int = 0,
    debate_inner_round: int = 0,
    prior_reviewer_feedback: str = "",
) -> None:
    state_file.write_text(
        json.dumps(
            {
                "topic": topic,
                "rounds": rounds,
                "models": models,
                "config": {
                    "min_rounds_before_stop": cfg.min_rounds_before_stop,
                    "max_rounds": cfg.max_rounds,
                    "max_response_chars": cfg.max_response_chars,
                    "max_paragraphs": cfg.max_paragraphs,
                    "export_best_consensus": cfg.export_best_consensus,
                    "prompt_language": cfg.prompt_language,
                    "drift_check_interval": cfg.drift_check_interval,
                    "max_review_cycles": cfg.max_review_cycles,
                    "max_inner_debate_rounds": cfg.max_inner_debate_rounds,
                },
                "reference_count": reference_count,
                "stop_reason": stop_reason,
                "status": status,
                "stage_statuses": stage_statuses or {},
                "review_cycles": review_cycles or [],
                "debate_review_cycle": debate_review_cycle,
                "debate_inner_round": debate_inner_round,
                "prior_reviewer_feedback": prior_reviewer_feedback,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _load_chat_resume_state(
    run_dir: Path,
    topic: str,
    models: dict[str, str],
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

    state_models = state.get("models", {})
    if not isinstance(state_models, dict):
        return None, False
    for role, model in models.items():
        if state_models.get(role) != model:
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


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

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
            drift_check_interval=max(1, int(cfg.get("drift_check_interval", defaults.drift_check_interval))),
            max_review_cycles=max(0, int(cfg.get("max_review_cycles", defaults.max_review_cycles))),
            max_inner_debate_rounds=max(0, int(cfg.get("max_inner_debate_rounds", defaults.max_inner_debate_rounds))),
        )
    except Exception:
        return defaults


# ---------------------------------------------------------------------------
# Reference collection (DeepXiv-primary)
# ---------------------------------------------------------------------------

def _collect_chat_references(topic: str, min_references: int) -> list[dict[str, Any]]:
    refs = collect_references_deepxiv_primary(topic)
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
        extra = collect_references_deepxiv_primary(q)
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


def _format_references(refs: list[dict[str, Any]]) -> str:
    """Format references as a markdown table."""
    lines = ["| # | source | id | year | citations | title | abstract | url |", "|---|---|---|---|---|---|---|---|"]
    for i, ref in enumerate(refs, 1):
        abstract = str(ref.get("abstract", "")).strip()[:320]
        lines.append(
            f"| {i} | {ref.get('source', '')} | {ref.get('id', '')} | {ref.get('year', 0)} | "
            f"{ref.get('citation_count', 0)} | {ref.get('title', '')} | {abstract} | {ref.get('url', '')} |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Chat generation and prompt builders
# ---------------------------------------------------------------------------

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


def _build_proposer_user_prompt(
    round_id: int, topic: str, reference_brief: str, prior_summary: str,
    min_references: int, language: str,
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
    round_id: int, topic: str, reference_brief: str, proposer_output: str,
    min_references: int, language: str,
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
    round_id: int, topic: str, proposer_output: str, skeptic_output: str, language: str,
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


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

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


def _parse_yaml_block(text: str) -> dict:
    """Extract the last YAML fenced block from text."""
    for fence in ("```yaml", "```yml"):
        idx = text.rfind(fence)
        if idx == -1:
            continue
        after = text[idx + len(fence):]
        end = after.find("```")
        if end == -1:
            continue
        yaml_str = after[:end].strip()
        try:
            data = yaml.safe_load(yaml_str)
            if isinstance(data, dict):
                return data
        except yaml.YAMLError:
            continue
    return {}


def _extract_revised_memo(text: str) -> str:
    """Extract the content after a # REVISED_MEMO heading."""
    m = re.search(r"#\s*REVISED_MEMO\s*\n(.*)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_summary_anchor(moderator_output: str) -> str:
    text = re.sub(r"\s+", " ", moderator_output).strip()
    if len(text) <= 220:
        return text
    return text[:220] + "..."


def _title_key(ref: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(ref.get("title", "")).strip()).lower()


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

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


def _write_round_artifacts(chat_dir: Path, record: dict[str, Any]) -> None:
    rid = int(record["round_id"])
    (chat_dir / f"round_{rid:02d}_proposer.md").write_text(record["proposer"].strip() + "\n", encoding="utf-8")
    (chat_dir / f"round_{rid:02d}_skeptic.md").write_text(record["skeptic"].strip() + "\n", encoding="utf-8")
    (chat_dir / f"round_{rid:02d}_moderator.md").write_text(record["moderator"].strip() + "\n", encoding="utf-8")
    (chat_dir / f"round_{rid:02d}.md").write_text(
        "\n\n".join([
            f"# Round {rid}",
            f"time: {record.get('round_started_at', '')} -> {record.get('round_completed_at', '')}",
            f"decision(raw/effective): {record.get('judge_decision_raw', '')} / {record.get('judge_decision_effective', '')}",
            f"## Proposer\n{record['proposer'].strip()}",
            f"## Skeptic\n{record['skeptic'].strip()}",
            f"## Moderator\n{record['moderator'].strip()}",
        ]) + "\n",
        encoding="utf-8",
    )


def _write_interim_outputs(
    run_dir: Path, topic: str, cfg: ChatModeConfig,
    refs: list[dict[str, Any]], rounds: list[dict[str, Any]], stop_reason: str,
) -> None:
    (run_dir / "CHAT_TRANSCRIPT.md").write_text(_build_transcript(topic, rounds), encoding="utf-8")
    _write_interim_consensus(topic=topic, rounds=rounds, output_file=run_dir / "BEST_CONSENSUS.md")


def _write_interim_consensus(topic: str, rounds: list[dict[str, Any]], output_file: Path) -> None:
    if not rounds:
        return
    last = rounds[-1]
    content = [
        "# BEST_CONSENSUS", "",
        "_INTERIM DRAFT: generated during running process; final version will be refined at completion._", "",
        f"topic: {topic}",
        f"latest_round: {last.get('round_id')}",
        f"decision(raw/effective): {last.get('judge_decision_raw', last.get('judge_decision'))} / {last.get('judge_decision_effective', last.get('judge_decision'))}",
        f"timestamp: {last.get('round_completed_at', '')}", "",
        "## Latest Moderator Summary", "",
        str(last.get("moderator", "")).strip(), "",
    ]
    output_file.write_text("\n".join(content), encoding="utf-8")


def _build_transcript(topic: str, rounds: list[dict[str, Any]]) -> str:
    lines = ["# CHAT_TRANSCRIPT", "", f"topic: {topic}", ""]
    for item in rounds:
        rid = int(item["round_id"])
        lines.extend([
            f"## Round {rid}", "",
            f"time: {item.get('round_started_at', '')} -> {item.get('round_completed_at', '')}",
            f"decision(raw/effective): {item.get('judge_decision_raw', '')} / {item.get('judge_decision_effective', '')}",
            "", f"### Proposer\n{item['proposer']}", "",
            f"### Skeptic\n{item['skeptic']}", "",
            f"### Moderator\n{item['moderator']}", "",
            f"Decision: {item.get('judge_decision', 'CONTINUE')}", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _write_review_cycles_report(run_dir: Path, review_cycles: list[dict[str, Any]]) -> None:
    lines = ["# Review Cycles Report", ""]
    for cycle in review_cycles:
        lines.extend([
            f"## Review Cycle {cycle.get('review_cycle', '?')}", "",
            f"Decision: {cycle.get('review_decision', 'UNKNOWN')}",
            f"Inner rounds completed: {cycle.get('inner_rounds_completed', 0)}", "",
            f"### Reviewer Output", "",
            str(cycle.get("reviewer_output", "")), "",
        ])
    (run_dir / "REVIEW_CYCLES.md").write_text("\n".join(lines), encoding="utf-8")


def _build_index(
    run_dir: Path, cfg: ChatModeConfig, reference_count: int,
    rounds: list[dict[str, Any]], stop_reason: str,
    consensus_file: Path | None, review_cycles: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        "# CHAT_MODE_INDEX", "",
        "This run uses the full chat-mode pipeline (9 stages) with nested review cycles.", "",
        f"- min_rounds_before_stop: {cfg.min_rounds_before_stop}",
        f"- max_rounds_soft_target: {'disabled' if cfg.max_rounds == 0 else cfg.max_rounds}",
        f"- drift_check_interval: {cfg.drift_check_interval}",
        f"- max_review_cycles: {cfg.max_review_cycles}",
        f"- max_inner_debate_rounds: {cfg.max_inner_debate_rounds}",
        f"- prompt_language: {cfg.prompt_language}",
        f"- stop_reason: {stop_reason}", "",
        "| file | purpose |",
        "|---|---|",
        "| TOPIC_CHAT.txt | Topic input |",
        "| REFERENCES.md | Reference list with abstracts (DeepXiv primary) |",
        "| LITERATURE_MAP.md | Literature mapping |",
        "| IDEA_REPORT.md | Candidate ideas |",
        "| FINAL_PROPOSAL.md | Final proposal |",
        "| EVIDENCE_TABLE.md | Claim-evidence table |",
        "| EXPERIMENT_PLAN.md | Experiment plan |",
        "| CHAT_TRANSCRIPT.md | Full conversation transcript |",
        "| BEST_CONSENSUS.md | Condensed best consensus |",
        "| RESEARCH_DECISION_MEMO.md | Final research decision memo |",
        "| AUTO_REVIEW.md | Auto-review logs |",
        "| REVIEW_CYCLES.md | Review cycles report |",
        "| chat_mode_state.json | Structured state with timestamps |",
        "| chat_rounds/ | Per-round artifacts |", "",
        f"completed_debate_rounds: {len(rounds)}",
        f"completed_review_cycles: {len(review_cycles or [])}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _export_best_consensus(
    client: LLMClient, model: str, topic: str, rounds: list[dict[str, Any]],
    refs: list[dict[str, Any]], output_file: Path,
    max_chars: int, max_paragraphs: int, language: str,
) -> Path:
    digest_lines: list[str] = []
    for item in rounds:
        digest_lines.append(
            f"R{item['round_id']} | P: {_extract_summary_anchor(str(item.get('proposer', '')))} | "
            f"S: {_extract_summary_anchor(str(item.get('skeptic', '')))} | "
            f"M: {_extract_summary_anchor(str(item.get('moderator', '')))} | "
            f"D: {item.get('judge_decision', 'CONTINUE')}"
        )

    system_prompt = localized_text(
        language,
        "You are the research lead. Distill the debate into one executable and falsifiable consensus plan. "
        "Keep it concise, evidence-bound, and decision-oriented.",
        "你是研究负责人。基于完整辩论提炼一个可执行、可验证、可落地的最优共识方案。保持精炼、证据绑定与决策导向。",
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
            f"Debate digest:\n{chr(10).join(digest_lines)}"
        ),
        (
            f"主题: {topic}\n\n"
            "请输出精简版共识方案，要求：\n"
            "1) 不超过3段，表达尽量精炼。\n"
            "2) 明确最终主方案、关键风险、最先执行的3步。\n"
            "3) 每个核心判断都要能被文献线索支撑（可用[1][2]引用标记）。\n"
            "4) 避免形式化证明和冗长铺垫。\n\n"
            f"辩论摘要:\n{chr(10).join(digest_lines)}"
        ),
    )
    text = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.35)
    content = "# BEST_CONSENSUS\n\n" + text.strip() + "\n"
    output_file.write_text(content, encoding="utf-8")
    return output_file


def _backfill_round_timestamps(
    rounds: list[dict[str, Any]], chat_dir: Path,
    min_rounds_before_stop: int, fallback_timestamp: str,
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
        item.setdefault("reply_timestamps", {
            "proposer": item.get("proposer_completed_at", ts),
            "skeptic": item.get("skeptic_completed_at", ts),
            "moderator": item.get("moderator_completed_at", ts),
        })

        raw = str(item.get("judge_decision_raw", item.get("judge_decision", "CONTINUE"))).strip() or "CONTINUE"
        eff = str(item.get("judge_decision_effective", item.get("judge_decision", raw))).strip() or raw
        if raw.startswith("STOP") and rid < min_rounds_before_stop:
            eff = "CONTINUE_MIN_ROUNDS_NOT_MET"
        item["judge_decision_raw"] = raw
        item["judge_decision_effective"] = eff
        item["judge_decision"] = eff
