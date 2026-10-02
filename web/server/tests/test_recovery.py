"""Recovery routing and public diagnostics; real agents are never started."""
import json
import sqlite3

import pytest

from arc_arena.artifacts import Artifacts
from arc_arena.jobs import JobError
from test_jobs import make_manager, USER, _wait


def paused_run(manager, *, protocol=False, discover_first=True, decision="discuss"):
    run_id = "run_recovery"
    key = "survey" if protocol else "idea1.check.protocol_retry1"
    state = {"discover_first": discover_first}
    if not protocol:
        state.update(pending_task=key, pending_evidence_requests=[{
            "question": "关键文献是否已有同类分层实验？", "target_source_ids": ["src_missing"]}])
    run = {"run_id": run_id, "mode": "discover",
           "status": "PAUSED_PROTOCOL" if protocol else "PAUSED_EXTERNAL",
           "stop_reason": "INVALID_OUTPUT_AFTER_REPAIR" if protocol else "critical_source_unavailable",
           "state": state, "created_at": "2026-09-12T00:00:00+00:00"}
    artifact = f"runs/{run_id}/tasks/paused.json"
    task = {"task_id": run_id + "." + key, "status": run["status"],
            "response_artifact_path": artifact,
            "error": run["stop_reason"] if protocol else None}
    snapshot = {"response": {"message": {
        "content": json.dumps({"result_status": "needs_evidence", "result": {"note": {"decision": decision}}}),
        "reasoning_content": "private reasoning must not be exposed"}},
        "messages": [{"content": "private prompt must not be exposed"}],
        "repair_validation_errors": ["already corrected error"]}
    if protocol:
        snapshot["final_validation_errors"] = [{"loc": ["result", "source_notes", 1],
            "msg": "source_access_exceeds_retrieved_material:src_metadata", "input": "private rejected input"}]
    path = manager.cfg.arc_db.parent / "artifacts" / artifact
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    with sqlite3.connect(manager.cfg.arc_db) as db:
        db.executescript("CREATE TABLE runs(id TEXT PRIMARY KEY, data TEXT);"
                         "CREATE TABLE tasks(id TEXT PRIMARY KEY, run_id TEXT, data TEXT);")
        db.execute("INSERT INTO runs VALUES(?,?)", (run_id, json.dumps(run)))
        db.execute("INSERT INTO tasks VALUES(?,?,?)", (task["task_id"], run_id, json.dumps(task)))
    return run, path


def test_discover_evidence_pause_resumes_main_workflow_even_with_discuss(tmp_path):
    manager, cfg = make_manager(tmp_path)
    run, _ = paused_run(manager)
    params = manager.validate_params("resume", {"run_id": run["run_id"]})
    argv = manager._build_argv("resume", params, "unused")
    assert argv[-2:] == ["resume", run["run_id"]]
    assert "--defer-evidence" not in argv
    detail = Artifacts(manager.store, cfg.arc_reports).run_detail(run["run_id"])
    assert detail["pause_recovery"] == {
        "kind": "evidence", "action": "resume", "task_key": "idea1.check.protocol_retry1", "actionable": True}
    diagnostics = detail["pause_diagnostics"]
    assert diagnostics["task_id"].endswith(".idea1.check.protocol_retry1")
    assert diagnostics["evidence_requests"][0]["source_ids"] == ["src_missing"]
    # A repaired output that then requests evidence must not show stale format errors.
    assert diagnostics["errors"] == []
    assert "private" not in json.dumps(detail)
    assert manager.store.get_run(run["run_id"]) == run
    job_id = manager.submit("resume", params, USER)["job_id"]
    result = _wait(lambda: (lambda value: value if value["job"]["status"] != "running" else None)(manager.status(job_id)))
    assert result["job"]["status"] == "completed"


def test_protocol_pause_keeps_retry_and_public_validation_details(tmp_path):
    manager, cfg = make_manager(tmp_path)
    run, _ = paused_run(manager, protocol=True)
    argv = manager._build_argv("resume", {"run_id": run["run_id"]}, "unused")
    assert argv[5:9] == ["retry-task", run["run_id"], "--task-key", "survey"]
    detail = Artifacts(manager.store, cfg.arc_reports).run_detail(run["run_id"])
    assert detail["pause_recovery"]["action"] == "retry-task"
    diagnostics = detail["pause_diagnostics"]
    assert diagnostics["errors"] == ["result.source_notes.1: source_access_exceeds_retrieved_material:src_metadata"]
    public = json.dumps(diagnostics)
    assert "private" not in public and "already corrected" not in public
    assert manager.store.get_run(run["run_id"]) == run


def test_rejected_recovery_is_failed_without_changing_paused_arc(tmp_path):
    manager, cfg = make_manager(tmp_path)
    run, _ = paused_run(manager, protocol=True)
    cfg.arc_bin.write_text("#!/usr/bin/env python3\nimport sys\nprint('EVIDENCE_DEFERRAL_REQUIRES_VALID_LIMITED_DRAFT')\nsys.exit(2)\n")
    job_id = manager.submit("resume", {"run_id": run["run_id"]}, USER)["job_id"]
    result = _wait(lambda: (lambda value: value if value["job"]["status"] != "running" else None)(manager.status(job_id)))
    assert result["job"]["status"] == "failed"
    assert "exit code 2" in result["job"]["error"]
    assert "EVIDENCE_DEFERRAL_REQUIRES_VALID_LIMITED_DRAFT" in result["job"]["error"]
    assert result["progress"]["status"] == "PAUSED_PROTOCOL"
    assert manager.store.get_run(run["run_id"]) == run
    detail = Artifacts(manager.store, cfg.arc_reports, manager).run_detail(run["run_id"])
    assert "EVIDENCE_DEFERRAL_REQUIRES_VALID_LIMITED_DRAFT" in detail["pause_diagnostics"]["recovery_error"]
    assert detail["run"]["status"] == "PAUSED_PROTOCOL"


@pytest.mark.parametrize("decision,allowed", [("discuss", False), ("lead", True), ("drop", True)])
def test_other_workflows_keep_explicit_deferral_constraint(tmp_path, decision, allowed):
    manager, _ = make_manager(tmp_path)
    run, _ = paused_run(manager, discover_first=False, decision=decision)
    recovery = manager.store.pause_recovery(run)
    assert recovery["kind"] == "defer"
    assert recovery["actionable"] is allowed
    if allowed:
        params = manager.validate_params("resume", {"run_id": run["run_id"]})
        assert manager._build_argv("resume", params, "unused")[-1] == "--defer-evidence"
    else:
        with pytest.raises(JobError, match="证据延期"):
            manager.submit("resume", {"run_id": run["run_id"]}, USER)
        assert manager.list_jobs() == []


def test_diagnostics_are_bounded_and_do_not_read_outside_artifacts(tmp_path):
    manager, _ = make_manager(tmp_path)
    run, path = paused_run(manager, protocol=True)
    snapshot = json.loads(path.read_text())
    snapshot["final_validation_errors"] = ["x" * 2100 for _ in range(12)]
    path.write_text(json.dumps(snapshot))
    diagnostics = manager.store.pause_diagnostics(run)
    assert diagnostics["truncated"] is True
    assert len(diagnostics["errors"]) == 10
    assert all(len(error) == 2000 for error in diagnostics["errors"])
    outside = tmp_path / "outside.json"
    outside.write_text('{"final_validation_errors":["private file"]}')
    with sqlite3.connect(manager.cfg.arc_db) as db:
        task = manager.store.get_task(run["run_id"] + ".survey")
        task["response_artifact_path"] = str(outside)
        db.execute("UPDATE tasks SET data=? WHERE id=?", (json.dumps(task), task["task_id"]))
    diagnostics = manager.store.pause_diagnostics(run)
    assert diagnostics["details_available"] is False
    assert "private file" not in json.dumps(diagnostics)


def test_missing_protocol_task_is_reported_before_spawning(tmp_path):
    manager, _ = make_manager(tmp_path)
    run, _ = paused_run(manager, protocol=True)
    with sqlite3.connect(manager.cfg.arc_db) as db:
        db.execute("DELETE FROM tasks")
    recovery = manager.store.pause_recovery(run)
    assert recovery["actionable"] is False
    with pytest.raises(JobError, match="暂停任务"):
        manager.submit("resume", {"run_id": run["run_id"]}, USER)
    assert manager.list_jobs() == []


def identity_retry(manager):
    run, _ = paused_run(manager, protocol=True)
    rid = run["run_id"]
    key = "survey.protocol_retry1"
    previous = rid + ".survey"
    subject = {"campaign_id": "campaign_1", "run_id": rid, "card_id": None, "card_version": None}
    inputs = {"subject": subject, "payload": {"protocol_retry": {"previous_task_id": previous}}}
    run["stop_reason"] = "SUBJECT_OR_TASK_MISMATCH"
    run["state"].update(task_retries={"survey": [{"replacement_key": key}]}, task_inputs={key: inputs})
    artifact = f"runs/{rid}/tasks/retry.json"
    path = manager.cfg.arc_db.parent / "artifacts" / artifact
    envelope = {"task_id": previous, "subject": dict(subject), "result": {"unmodified": True}}
    path.write_text(json.dumps({"response": {"message": {"content": json.dumps(envelope)}}}))
    task = {"task_id": rid + "." + key, "status": "PAUSED_PROTOCOL", "accepted_result": None,
            "error": "SUBJECT_OR_TASK_MISMATCH", "response_artifact_path": artifact}
    with sqlite3.connect(manager.cfg.arc_db) as db:
        db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(run), rid))
        db.execute("INSERT INTO tasks VALUES(?,?,?)", (task["task_id"], rid, json.dumps(task)))
    return run, key, path, envelope


def test_explicit_previous_identity_can_resume_saved_response(tmp_path):
    manager, _ = make_manager(tmp_path)
    run, key, path, _ = identity_retry(manager)
    before = path.read_bytes()
    assert manager.store.paused_task_key(run["run_id"], run) == key
    plan = manager.store.pause_recovery(run)
    assert plan["action"] == "resume" and plan["actionable"]
    assert manager._build_argv("resume", {"run_id": run["run_id"]}, "unused")[-2:] == ["resume", run["run_id"]]
    assert manager.store.pause_diagnostics(run)["task_id"] == run["run_id"] + "." + key
    assert path.read_bytes() == before
    assert manager.store.get_run(run["run_id"]) == run


@pytest.mark.parametrize("mismatch", ["subject", "missing_subject_field", "other_task", "missing_predecessor", "different_run", "non_json"])
def test_unproven_identity_mismatches_still_require_retry(tmp_path, mismatch):
    manager, _ = make_manager(tmp_path)
    run, key, path, envelope = identity_retry(manager)
    if mismatch == "subject":
        envelope["subject"]["card_id"] = "another_card"
    elif mismatch == "missing_subject_field":
        envelope["subject"].pop("campaign_id")
    elif mismatch == "other_task":
        envelope["task_id"] = run["run_id"] + ".unrelated"
    elif mismatch == "missing_predecessor":
        run["state"]["task_inputs"][key]["payload"]["protocol_retry"].pop("previous_task_id")
    elif mismatch == "different_run":
        envelope["task_id"] = "run_other.survey"
        run["state"]["task_inputs"][key]["payload"]["protocol_retry"]["previous_task_id"] = envelope["task_id"]
    raw = "{" if mismatch == "non_json" else json.dumps(envelope)
    path.write_text(json.dumps({"response": {"message": {"content": raw}}}))
    assert manager.store.pause_recovery(run)["action"] == "retry-task"


def test_accepted_replacement_is_not_reported_as_old_failure(tmp_path):
    manager, _ = make_manager(tmp_path)
    run, key, _, _ = identity_retry(manager)
    with sqlite3.connect(manager.cfg.arc_db) as db:
        task = manager.store.get_task(run["run_id"] + "." + key)
        task.update(status="ACCEPTED", accepted_result={"result_status": "complete"})
        db.execute("UPDATE tasks SET data=? WHERE id=?", (json.dumps(task), task["task_id"]))
    assert manager.store.paused_task_key(run["run_id"], run) is None


@pytest.mark.parametrize("stage", ["sketch", "triage"])
def test_candidate_handoff_progress_keeps_raw_status_and_unverified_marker(tmp_path, stage):
    manager, _ = make_manager(tmp_path)
    run, _ = paused_run(manager)
    run["status"] = "RUNNING"
    run["stop_reason"] = None
    key = f"idea1.{stage}"
    task_id = run["run_id"] + "." + key
    marker = {"source_task_id": task_id, "result_status": "needs_evidence",
              "research_verified": False, "handoff": "candidate_prestudy"}
    run["state"][key + "_provisional"] = marker
    with sqlite3.connect(manager.cfg.arc_db) as db:
        db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(run), run["run_id"]))
    log = tmp_path / "handoff.log"
    log.write_text("\n".join(json.dumps(event) for event in [
        {"run_id": run["run_id"], "task_id": task_id, "status": "PAUSED_EXTERNAL"},
        {"run_id": run["run_id"], "task_id": run["run_id"] + ".idea1.check", "status": "RESERVED"},
    ]))
    progress = manager._progress("discover", run["run_id"], str(log))
    assert progress["status"] == "RUNNING"
    assert progress["current"] == "idea1.check"
    assert progress["tasks"][0] == {"task_id": key, "status": "PAUSED_EXTERNAL",
                                     "handoff": "candidate_prestudy", "research_verified": False}
    assert progress["tasks"][1] == {"task_id": "idea1.check", "status": "RESERVED"}
    assert manager.store.get_run(run["run_id"]) == run
    # Without the full explicit marker, the same raw pause remains an ordinary pause.
    run["state"][key + "_provisional"].pop("research_verified")
    with sqlite3.connect(manager.cfg.arc_db) as db:
        db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(run), run["run_id"]))
    progress = manager._progress("discover", run["run_id"], str(log))
    assert progress["tasks"][0] == {"task_id": key, "status": "PAUSED_EXTERNAL"}



def read_length_alias_pause(manager):
    run, path = paused_run(manager, protocol=True)
    run["stop_reason"] = "TOOL_CORRECTION_TARGET_CHANGED"
    failures, calls = [], []
    for document, offset, limit in [("2603.18373v1", 13000, 11500), ("2608.11024v1", 3000, 5000), ("2608.11024v1", 32500, 6500)]:
        failures.append({"name": "read_paper", "arguments": {"document_id": document, "offset": offset, "limit": limit},
                         "errors": [{"path": ["limit"], "validator": "additionalProperties", "expected": False}],
                         "parameters": {"properties": {"document_id": {}, "offset": {}, "limit_chars": {"type": "integer"}}}})
        calls.append({"type": "function", "function": {"name": "read_paper",
                     "arguments": json.dumps({"document_id": document, "offset": offset, "limit_chars": limit})}})
    saved = {"tool_correction_failure": "TOOL_CORRECTION_TARGET_CHANGED", "pending_model": None, "pending_tool": None,
             "tool_correction": {"phase": "awaiting", "failures": failures},
             "response": {"completed_at": "2026-09-12T12:00:00Z", "message": {"tool_calls": calls}}}
    path.write_text(json.dumps(saved))
    with sqlite3.connect(manager.cfg.arc_db) as db:
        task = manager.store.get_task(run["run_id"] + ".survey")
        task["error"] = "TOOL_CORRECTION_TARGET_CHANGED"
        db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(run), run["run_id"]))
        db.execute("UPDATE tasks SET data=? WHERE id=?", (json.dumps(task), task["task_id"]))
    return run, path, saved


def test_saved_equal_read_length_alias_batch_resumes_without_rewriting_response(tmp_path):
    manager, _ = make_manager(tmp_path)
    run, path, _ = read_length_alias_pause(manager)
    before = path.read_bytes()
    plan = manager.store.pause_recovery(run)
    assert plan["action"] == "resume" and plan["actionable"]
    assert manager._build_argv("resume", {"run_id": run["run_id"]}, "unused")[-2:] == ["resume", run["run_id"]]
    assert path.read_bytes() == before
    assert manager.store.get_run(run["run_id"]) == run


@pytest.mark.parametrize("change", ["source", "offset", "length", "length_type", "tool", "count", "order", "extra_field", "missing_field", "invalid_other_field", "no_schema_alias", "not_settled"])
def test_changed_or_unproven_read_corrections_still_use_retry_task(tmp_path, change):
    manager, _ = make_manager(tmp_path)
    run, path, saved = read_length_alias_pause(manager)
    calls = saved["response"]["message"]["tool_calls"]
    args = json.loads(calls[0]["function"]["arguments"])
    if change == "source": args["document_id"] = "another_paper"
    elif change == "offset": args["offset"] += 1
    elif change == "length": args["limit_chars"] += 1
    elif change == "length_type": args["limit_chars"] = float(args["limit_chars"])
    elif change == "extra_field": args["refresh"] = True
    elif change == "missing_field": args.pop("offset")
    calls[0]["function"]["arguments"] = json.dumps(args)
    if change == "tool": calls[0]["function"]["name"] = "read_web"
    elif change == "count": calls.pop()
    elif change == "order": calls.reverse()
    elif change == "invalid_other_field": saved["tool_correction"]["failures"][0]["errors"].append({"path": ["offset"], "validator": "type"})
    elif change == "no_schema_alias": saved["tool_correction"]["failures"][0]["parameters"]["properties"].pop("limit_chars")
    elif change == "not_settled": saved["pending_model"] = {"call_id": "outstanding_call"}
    path.write_text(json.dumps(saved))
    assert manager.store.pause_recovery(run)["action"] == "retry-task"
