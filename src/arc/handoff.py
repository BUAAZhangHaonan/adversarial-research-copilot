"""Idempotent preparation and result lookup for one requested light research stage."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os

from .config import Settings
from .external_idea import SelectedIdea, fingerprint
from .schemas import utc_now
from .store import StateError


class HandoffBusy(RuntimeError):
    """Another process is currently executing this stage."""


@contextmanager
def handoff_lock(store, handoff_id, *, wait=True, purpose="execute"):
    """One local executor per persisted request; the OS releases it on process exit."""
    root = store.db_path.parent / "handoff-locks"
    root.mkdir(mode=0o700, exist_ok=True)
    path = root / (fingerprint([purpose, handoff_id]) + ".lock")
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if path.stat().st_size == 0:
                stream.write(b"1")
                stream.flush()
            stream.seek(0)
            mode = msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK
            try:
                msvcrt.locking(stream.fileno(), mode, 1)
            except OSError as exc:
                raise HandoffBusy("handoff_running") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
            except BlockingIOError as exc:
                raise HandoffBusy("handoff_running") from exc
        yield


def _existing(store, handoff_id):
    with store._connect() as db:
        row = db.execute("SELECT * FROM external_handoffs WHERE id=?", (handoff_id,)).fetchone()
    return dict(row) if row else None


def handoff_record(store, handoff_id):
    row = _existing(store, handoff_id)
    if row is None:
        raise StateError("unknown_external_handoff")
    return json.loads(row["data"])


def _prepare(store, settings, request, signature):
    hid = request.handoff_id
    idea_id = request.idea_id or "idea_ext_" + fingerprint(["radar.idea.v1", hid])[:32]
    run_id = "run_" + fingerprint(["radar.stage.v1", hid])[:32]
    origin = request.origin.model_dump()
    previous = {}
    if request.idea_id:
        existing = store.get_lightweight_idea(idea_id)
        first_origin = existing.get("external_origin") or {}
        if (first_origin.get("system"), first_origin.get("direction_id")) != (
            origin["system"], origin["direction_id"]
        ):
            raise StateError("continuation_belongs_to_another_origin")
        _, previous = store.selected_idea_context(idea_id)
    seed, brief, mapping = request.register_materials(store)
    if previous:
        seed.source_ids=list(dict.fromkeys([*seed.source_ids, *previous["seed"]["source_ids"]]))
    field = brief.model_dump(mode="json")
    if previous.get("field_brief"):
        prior = previous["field_brief"]
        field = {**prior, "source_notes": list(prior.get("source_notes", []))}
        for note in brief.model_dump(mode="json")["source_notes"]:
            if note not in field["source_notes"]:
                field["source_notes"].append(note)
        field["search_limits"] = list(dict.fromkeys([*prior.get("search_limits", []),
                                                     *request.request.boundaries]))
    selected = {**previous, "idea_id": idea_id, "original_question": seed.question,
                "stage_focus": request.request.focus, "user_boundaries": request.request.boundaries,
                "seed": seed.model_dump(mode="json"), "latest_note": previous.get("latest_note"),
                "field_brief": field, "external_origin": origin, "research_profile": request.profile,
                "available_assets": request.assets, "resource_conditions": request.resource_conditions}
    body = {"handoff_id": hid, "idea_id": idea_id, "run_id": run_id, "origin": origin,
            "stage": request.request.stage, "payload": request.model_dump(mode="json"),
            "stage_input": selected, "source_mapping": mapping, "settings": settings.model_copy(update={"data_dir":settings.data_dir.resolve()}).model_dump(mode="json"),
            "imported_at": utc_now()}
    idea = {"idea_id": idea_id, "external_origin": origin, "initial_context": selected,
            "topic": seed.question, "seed": selected["seed"], "note": None, "status": "selected",
            "created_at": body["imported_at"]}
    with store._transaction() as db:
        if not request.idea_id:
            db.execute("INSERT INTO external_ideas VALUES(?,?)", (idea_id, json.dumps(idea, ensure_ascii=False)))
        db.execute("INSERT INTO external_handoffs VALUES(?,?,?,?,?)",
                   (hid, signature, idea_id, run_id, json.dumps(body, ensure_ascii=False)))
    return body


def import_selected(settings, request: SelectedIdea):
    from .cli import services

    store, _ = services(settings)
    signature = fingerprint(request.model_dump(mode="json"))
    with handoff_lock(store, request.handoff_id, purpose="prepare"):
        row = _existing(store, request.handoff_id)
        if row and row["payload_hash"] != signature:
            raise StateError("handoff_id_reused_for_different_immutable_input")
        body = json.loads(row["data"]) if row else _prepare(store, settings, request, signature)
        materialize_run(store, body)
    return body


def materialize_run(store, body):
    """The frozen handoff persists before the account and stage. Re-entry finishes preparation."""
    from .cli import new_run

    with store._connect() as db:
        created = db.execute("SELECT 1 FROM runs WHERE id=?", (body["run_id"],)).fetchone()
    if not created:
        frozen = Settings.model_validate(body["settings"]).model_copy(update={"data_dir":store.db_path.parent.resolve()})
        new_run(frozen, body["stage"], idea_id=body["idea_id"], budget=frozen.budget_cny,
                run_id=body["run_id"], frozen_idea_input=body["stage_input"])


def recover_registration(store, handoff_id):
    with handoff_lock(store, handoff_id, purpose="prepare"):
        body = handoff_record(store, handoff_id)
        materialize_run(store, body)
    return body
