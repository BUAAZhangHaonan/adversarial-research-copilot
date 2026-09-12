"""Close an unavailable-literature task once, without accepting its blocked draft."""
from __future__ import annotations

import json
from copy import deepcopy

from .discovery_models import CandidateCheck, FieldBrief, SketchResult, TriageResult
from .runtime import RuntimePaused
from .schemas import utc_now
from .workflows import WorkflowPause

EVIDENCE_PAUSES = {"critical_source_unavailable", "SOURCE_READ_NO_PROGRESS",
                   "TOOL_REMOTE_RESULT_UNKNOWN", "evidence_action_exhausted"}
CLOSURE_OUTPUT_FAILURES = {"INVALID_OUTPUT_AFTER_REPAIR", "UNEXPECTED_TOOL_CALLS",
                           "STOP_WITH_TOOL_CALLS", "SUBJECT_OR_TASK_MISMATCH"}
RECOVERABLE_OUTPUT_FAILURES = {"INVALID_OUTPUT_AFTER_REPAIR",
    "TOOL_ARGUMENTS_INVALID_AFTER_CORRECTION", "TOOL_CORRECTION_CALLS_MISMATCH",
    "TOOL_CORRECTION_REQUIRED"}
LIMIT_MESSAGE = "文献获取受限，本任务保留待查；未取得的材料不能用于证明新颖性、排除近邻或确认可行性。"
OUTPUT_LIMIT_MESSAGE = "本任务输出在一次纠错后仍未通过校验；仅用已保存材料作有限收尾，原失败稿不作为已核实结论。"


def _source_key(run, key):
    """Runtime errors can precede pending_task; follow the actual explicit revision."""
    candidate = run.state.get('pending_task') or key
    if candidate != key and not candidate.startswith(key + '.'):
        candidate = key
    revisions = run.state.get('task_retries', {})
    while revisions.get(candidate):
        candidate = revisions[candidate][-1]['replacement_key']
    return candidate


def validate_evidence_limit_result(envelope, payload):
    if not payload.get("evidence_limit_handoff") or envelope.result_status != "complete":
        return
    result = envelope.result
    if isinstance(result, CandidateCheck):
        if result.note.decision not in {"lead", "drop"}:
            raise ValueError("EVIDENCE_LIMIT_REQUIRES_LEAD_OR_DROP")
        if not any(x.strip() for x in result.note.limits):
            raise ValueError("EVIDENCE_LIMIT_MUST_RETAIN_UNRESOLVED_LIMITS")
    elif isinstance(result, TriageResult) and result.action == "investigate":
        raise ValueError("EVIDENCE_LIMIT_TRIAGE_REQUIRES_PARK_OR_DROP")
    elif isinstance(result, FieldBrief) and not any(x.strip() for x in result.search_limits):
        raise ValueError("EVIDENCE_LIMIT_SURVEY_REQUIRES_SEARCH_LIMITS")
    elif isinstance(result, SketchResult) and result.action == "stop":
        raise ValueError("EVIDENCE_LIMIT_SKIP_THIS_DRAW_NOT_THE_BATCH")


def _save(engine, run_id, key, entry):
    limits = dict(engine.store.get_run(run_id).state.get("evidence_limits", {}))
    limits[key] = entry
    engine.checkpoint(run_id, evidence_limits=limits)
    engine.store.save_artifact(f"runs/{run_id}/evidence-limits/{key}.json",
        json.dumps(entry, ensure_ascii=False, indent=2))


def _handoff(engine, run_id, key, reason, payload):
    run = engine.store.get_run(run_id)
    source_key = _source_key(run, key)
    task_id = run_id + "." + source_key
    record = engine.store.get_task(task_id)
    draft, response_path = None, None
    if record is not None and record.response_artifact_path:
        response_path = record.response_artifact_path
        try:
            saved = json.loads(engine.store.read_artifact(response_path))
            raw = ((saved.get("response") or {}).get("message") or {}).get("content")
            parsed = json.loads(raw) if raw else {}
            # Only the structured proposal, never private reasoning or an accepted verdict.
            draft = parsed.get("result")
        except (ValueError, FileNotFoundError, TypeError):
            pass
    limit_message = OUTPUT_LIMIT_MESSAGE if reason in RECOVERABLE_OUTPUT_FAILURES else LIMIT_MESSAGE
    entry = {"reason": limit_message, "pause_reason": reason, "status": "closing",
        "source_task_id": task_id, "response_artifact_path": response_path,
        "closure_key": key + ".with_available_evidence", "created_at": utc_now(),
        "unresolved_evidence_requests": run.state.get("pending_evidence_requests", []),
        "unresolved_capability_requests": run.state.get("pending_capability_requests", [])}
    frozen = deepcopy(run.state.get("task_inputs", {}).get(source_key, {}).get("payload", payload or {}))
    from .discovery_validation import repair_source_catalog
    frozen['retrieved_source_catalog'] = repair_source_catalog(
        engine.store, frozen, engine.runtime.tool_trace(task_id))
    # Reuse a bounded set of actual retrieved passages; full traces remain in artifacts.
    material, remaining = [], 24000
    for item in reversed(engine.runtime.tool_trace(task_id)):
        if item.get("status") != "completed":
            continue
        body = item.get("result") or {}
        if body.get("is_error"):
            continue
        serialized = json.dumps(body, ensure_ascii=False)
        excerpt = serialized[:min(6000, remaining)]
        from .runtime import reference_ids, SOURCE_REF_KEYS
        material.append({"tool": item.get("name"),
                         "source_ids": sorted(reference_ids([body, item.get("source_ids", [])], SOURCE_REF_KEYS)
                                              | set(item.get("source_ids", []))),
                         "result_excerpt": excerpt,
                         "excerpt_truncated": len(excerpt) < len(serialized)})
        remaining -= len(excerpt)
        if len(material) >= 6 or remaining <= 0:
            break
    frozen["evidence_limit_handoff"] = {
        "reason": limit_message, "pause_reason": reason, "source_task_id": task_id,
        "unresolved_evidence_requests": entry["unresolved_evidence_requests"],
        "unaccepted_draft": draft, "recent_material_excerpts": list(reversed(material)),
        "instruction": "本次只利用已取得的材料收尾，不再检索。返回complete表示有限结论已写完，不表示证据已齐全。"
            "缺证必须列在限制和下一待查问题中，不得写成没有相关工作。CHECK/DEVELOP/PRESSURE仅可lead或drop；"
            "只有现有材料足以否定候选才drop，单纯读不到文献应lead。TRIAGE用park或有依据的drop；"
            "SURVEY注明调研范围限制；SKETCH可以提出明确待查的假设，无法形成想法则skip，不能终止其余抽卡。"
            "不添加实验结果，不把未读全文写成已读。仍沿用原结果结构。"}
    return entry, frozen


def _previous_evidence_pause(engine, run_id, key, role=None, task=None):
    """An already received blocked result needs no replay under a changed tool profile."""
    run = engine.store.get_run(run_id)
    source_key = _source_key(run, key)
    record = engine.store.get_task(run_id + "." + source_key)
    if record is None or record.accepted_result is not None or record.status != "PAUSED_EXTERNAL":
        return None
    if record.error in EVIDENCE_PAUSES:
        return record.error
    if record.response_artifact_path:
        try:
            saved = json.loads(engine.store.read_artifact(record.response_artifact_path))
            raw = ((saved.get("response") or {}).get("message") or {}).get("content")
            value = json.loads(raw) if raw else {}
            if value.get("result_status") == "needs_evidence":
                result = value.get('result') or {}
                if ((role, task) == ('ideator', 'SKETCH') and result.get('action') == 'submit'
                        and isinstance(result.get('seed'), dict)) or (
                        (role, task) == ('editor', 'TRIAGE') and result.get('action') == 'investigate'):
                    # Re-enter normal validation of the saved response. The early
                    # stage may hand a provisional idea to CHECK without buying closure.
                    return None
                return "critical_source_unavailable"
        except (ValueError, FileNotFoundError, TypeError):
            pass
    return None


async def call_with_evidence_limits(engine, run_id, key, role, task, payload=None, **kwargs):
    """Research access failure affects this result, not unrelated remaining draws."""
    run = engine.store.get_run(run_id)
    entry = run.state.get("evidence_limits", {}).get(key)
    if entry and entry["status"] == "parked":
        return None
    if not entry:
        reason = _previous_evidence_pause(engine, run_id, key, role, task)
        if reason is None:
            try:
                return await engine.call(run_id, key, role, task, payload=payload, **kwargs)
            except (WorkflowPause, RuntimePaused) as exc:
                if exc.reason not in EVIDENCE_PAUSES and not (
                        exc.status == 'PAUSED_PROTOCOL' and exc.reason in RECOVERABLE_OUTPUT_FAILURES):
                    raise
                reason = exc.reason
        entry, frozen = _handoff(engine, run_id, key, reason, payload)
        # Save the complete input before the new paid task, making resume deterministic.
        input_path = f"runs/{run_id}/evidence-limits/{key}.input.json"
        engine.store.save_artifact(input_path, json.dumps(frozen, ensure_ascii=False))
        entry["input_path"] = input_path
        _save(engine, run_id, key, entry)
    frozen = json.loads(engine.store.read_artifact(entry["input_path"]))
    try:
        result = await engine.call(run_id, entry["closure_key"], role, task,
            payload=frozen, tool_profile=[], on_admitted=kwargs.get("on_admitted"))
    except (WorkflowPause, RuntimePaused) as exc:
        if exc.reason not in EVIDENCE_PAUSES and not (
                exc.status == "PAUSED_PROTOCOL" and exc.reason in CLOSURE_OUTPUT_FAILURES):
            raise
        entry = {**entry, "status": "parked", "closure_failure": exc.reason}
        _save(engine, run_id, key, entry)
        return None
    entry = {**entry, "status": "limited"}
    _save(engine, run_id, key, entry)
    traces = list(dict.fromkeys([entry["source_task_id"], *engine.trace_tasks(run_id, entry["closure_key"])]))
    questions = list(entry.get('unresolved_evidence_requests', []))
    for question in engine.store.get_run(run_id).state.get(entry['closure_key'] + '_evidence_requests', []):
        if question not in questions:
            questions.append(question)
    engine.checkpoint(run_id, **{key: result.model_dump(mode="json"), key + "_trace_tasks": traces,
                               key + '_evidence_requests': questions})
    return result


def unavailable_brief(previous=None):
    body = deepcopy(previous) if previous else dict(overview="未取得可核查资料，本阶段尚未形成领域判断。",
        research_lines=[], openings=[], source_notes=[], search_limits=[])
    if LIMIT_MESSAGE not in body["search_limits"]:
        body["search_limits"].append(LIMIT_MESSAGE)
    return FieldBrief.model_validate(body)
