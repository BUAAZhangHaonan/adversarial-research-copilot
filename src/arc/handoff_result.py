"""Project an ARC research stage without rewriting its research or writer output."""
from __future__ import annotations

from .handoff import handoff_record
from .research_context import reference_ids, SOURCE_KEYS
from .stage_sources import trace_readings, public_url


def export_result(store, ledger, handoff_id):
    body = handoff_record(store, handoff_id)
    run = store.get_run(body["run_id"])
    state = run.state
    note = state.get("prestudy_note") or {}
    polish = state.get("polish")
    mapped = body["source_mapping"]
    imported = {row["source_id"] for row in mapped}
    selected = state.get("idea_input") or body["stage_input"]
    inherited = reference_ids([selected.get("latest_note"), selected.get("field_brief")], SOURCE_KEYS)
    source_notes = [
        *(selected.get("field_brief") or {}).get("source_notes", []),
        *(selected.get("latest_note") or {}).get("source_notes", []),
        *(state.get("field_brief") or {}).get("source_notes", []),
        *note.get("source_notes", []),
    ]
    cited = reference_ids([note.get("source_notes"), note.get("nearest_work"), polish],
                          {"source_id", "cited_source_ids"})
    ids = set(state.get("source_ids", [])) | cited | imported | inherited
    by_source = {}
    for n in source_notes:
        group = by_source.setdefault(n["source_id"], [])
        if n not in group:
            group.append(n)
    ids.update(by_source)
    traced = trace_readings(store, run.run_id) if run.status != "RUNNING" else {}
    ids.update(traced)
    # Include older Radar links only for sources delivered into this continuation.
    if body["payload"].get("idea_id") and inherited:
        import json
        with store._connect() as db:
            older = db.execute("SELECT json_extract(data,'$.source_mapping') FROM external_handoffs WHERE idea_id=? "
                               "AND rowid<(SELECT rowid FROM external_handoffs WHERE id=?) ORDER BY rowid",
                               (body["idea_id"],handoff_id)).fetchall()
        for row in older:
            for link in json.loads(row[0]):
                if link["source_id"] in inherited and link not in mapped:
                    mapped.append(link)
    directory = []
    for source in store.list_sources(ids=sorted(ids)):
        notes = by_source.get(source.source_id, [])
        levels = sorted(traced.get(source.source_id,set()) | {n["access"] for n in notes if n.get("access")} |
                        {s["access"] for s in mapped if s["source_id"] == source.source_id})
        directory.append({
            "source_id": source.source_id, "title": source.title, "url": public_url(source), "doi": source.doi,
            "arxiv_id": source.arxiv_id, "version": source.version, "source_type": source.source_type,
            "access_status": source.access_status, "content_complete": bool(source.content_path and source.content_complete),
            "representation_id":source.representation_id, "start_char":source.content_start_char,
            "total_chars":source.content_total_chars,
            "reading_level": levels[0] if len(levels) == 1 else (
                "multiple" if levels else "metadata" if source.access_status == "metadata_only" else "not_recorded"),
            "read_levels": levels, "source_notes": notes,
            "origin": ("radar" if source.source_id in imported else
                       "prior_stage" if source.source_id in inherited else "arc_stage"),
        })
    with store._connect() as db:
        execution = db.execute("SELECT started_at FROM handoff_executions WHERE handoff_id=?",
                               (handoff_id,)).fetchone()
    completed = run.status == "COMPLETED"
    execution_status = run.status.lower()
    if run.status == "RUNNING" and not execution:
        execution_status = "prepared"
    limited = bool(state.get("prestudy_evidence_limited") or state.get("evidence_limits"))
    draft_text = None
    if not polish and note:
        # This is ARC's own saved research report, even if POLISH failed.
        file = store.db_path.parent / "reports" / run.run_id / "ideas" / (body["idea_id"] + ".technical.md")
        if file.is_file():
            draft_text = file.read_text(encoding="utf-8")
    return {
        "schema_version":"radar.arc.prestudy.v1", "handoff_id":handoff_id, "idea_id":body["idea_id"],
        "run_id":run.run_id, "origin":body["origin"], "stage":run.mode, "focus":selected.get("stage_focus"),
        "execution_status":execution_status, "stop_reason":run.stop_reason,
        "research_decision":note.get("decision"), "current_understanding":note.get("current_understanding"),
        "next_question":note.get("next_question"), "evidence_limited":limited,
        "presentation_status":("polished" if polish else "draft" if note else "unavailable" if completed else "pending"),
        "presentation":polish, "polish_failure":state.get("polish_failure"),
        "draft":note or None, "draft_text":draft_text, "cited_source_ids":sorted(cited),
        "source_directory":directory, "source_mapping":mapped, "source_notes":note.get("source_notes", []),
        "previous_stage":selected.get("latest_note_origin"), "cost":ledger.summary(run.budget_account_id),
    }
