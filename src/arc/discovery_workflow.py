"""Discover short ideas first; preserve paid task boundaries and human handoff."""
from __future__ import annotations
from .discovery_models import FieldBrief, CandidateCheck
from .schemas import utc_now


from .research_context import build_discovery_context as context


def publish(engine, run_id):
    from .reports import render_run
    render_run(engine.store, run_id, engine.settings.data_dir.resolve() / "reports" / run_id)


def check_action_observed(trace, note):
    """A registered citation is not evidence of this task actually retrieving."""
    cited = {n.source_id for n in note.source_notes} | {w.source_id for w in note.nearest_work} | set(note.seed.source_ids)
    for item in trace:
        result = item.get("result") or {}
        if item.get("status") != "completed" or result.get("is_error"):
            continue
        ids = set(item.get("source_ids", [])) | set(result.get("source_ids", []))
        if result.get("source_id"): ids.add(result["source_id"])
        if item.get("name") in {"search_literature", "search_web"} and (not ids or cited & ids):
            return True
        if item.get("name") == "read_record" and result.get("content") and result.get("source_id") in cited:
            return True
        if item.get("name") in {"read_paper", "read_web"}:
            if any(source.get("source_id") in cited and source.get("content") for source in result.get("sources", [])):
                return True
    return False


def bound_check(result, trace):
    observed = check_action_observed(trace, result.note)
    if not observed:
        body = result.model_dump(mode="json")
        note = body["note"]
        note["limits"].append("本次任务未观察到与候选相关的有效检索或原文/缓存片段读取；预研结论仍待核查。")
        if note["decision"] == "discuss": note["decision"] = "lead"
        result = CandidateCheck.model_validate(body)
    return result, observed


def merge_updates(engine, run_id, updates):
    if not updates: return
    run = engine.store.get_run(run_id)
    brief = dict(run.state["field_brief"])
    notes = list(brief["source_notes"])
    for update in updates:
        value = update.model_dump(mode="json")
        if value not in notes: notes.append(value)
    if notes != brief["source_notes"]:
        brief["source_notes"] = notes
        engine.checkpoint(run_id, field_brief=FieldBrief.model_validate(brief).model_dump(mode="json"),
                          brief_version=run.state.get("brief_version", 1) + 1)


async def discover(engine, run_id):
    run = engine.store.get_run(run_id)
    if not run.state.get("field_brief"):
        brief = await engine.call(run_id, "survey", "scout", "SURVEY", payload=context(engine, run_id))
        engine.checkpoint(run_id, field_brief=brief.model_dump(mode="json"), brief_version=1)
        publish(engine, run_id)
    campaign = engine.store.get_campaign(run.campaign_id)
    # Stable draw keys include previously admitted failures on every resume.
    for ordinal in range(1, campaign.max_draws + 1):
        key = f"idea{ordinal}"
        run = engine.store.get_run(run_id)
        if run.state.get(key + "_done"):
            if run.state.get(key + ".sketch", {}).get("action") == "stop":
                engine.complete(run_id, "ideator_stopped")
                publish(engine, run_id)
                return
            continue
        if run.state.get("survey_refresh_used") and not run.state.get("survey_refresh_applied"):
            brief = await engine.call(run_id, "survey.refresh", "scout", "SURVEY", payload={
                **context(engine, run_id), "refresh_question": run.state["survey_refresh_question"]})
            engine.checkpoint(run_id, field_brief=brief.model_dump(mode="json"),
                              brief_version=run.state.get("brief_version", 1) + 1, survey_refresh_applied=True)
            run = engine.store.get_run(run_id)
        payload = {**context(engine, run_id), "draw_id": key,
                   "previous_directions": run.state.get("previous_directions", []),
                   "remaining_draws": campaign.max_draws - ordinal + 1}
        sketch = await engine.call(run_id, key + ".sketch", "ideator", "SKETCH", payload=payload,
            on_admitted=lambda k=key: engine.store.claim_draw(campaign.campaign_id, run_id + "." + k))
        record = engine.store.save_discovery_idea(run_id, key,
            seed=sketch.seed.model_dump(mode="json") if sketch.seed else None, sketch=sketch.model_dump(mode="json"))
        run = engine.store.get_run(run_id)
        ids = list(run.state.get("idea_ids", []))
        if record["idea_id"] not in ids: ids.append(record["idea_id"])
        updates = {"idea_ids": ids}
        if sketch.seed and not run.state.get("first_seed_at"): updates["first_seed_at"] = record["created_at"]
        engine.checkpoint(run_id, **updates)
        publish(engine, run_id)
        if sketch.action == "submit":
            seed = sketch.seed.model_dump(mode="json")
            archive = engine.store.lookup_archive(sketch.seed.question, limit=4)
            previous = engine.store.lookup_discovery_ideas(sketch.seed.question, exclude_run_id=run_id, limit=4)
            triage = await engine.call(run_id, key + ".triage", "editor", "TRIAGE", payload={
                **context(engine, run_id), "idea_id": record["idea_id"], "seed": seed,
                "local_archive": archive, "previous_ideas": previous})
            engine.store.save_discovery_idea(run_id, key, triage=triage.model_dump(mode="json"),
                status="pending" if triage.action == "investigate" else triage.action)
            publish(engine, run_id)
            if triage.action == "investigate":
                checked = await engine.call(run_id, key + ".check", "scout", "CHECK", payload={
                    **context(engine, run_id), "idea_id": record["idea_id"], "seed": seed,
                    "triage": triage.model_dump(mode="json")})
                checked, observed = bound_check(checked, engine.task_trace(run_id, key + ".check"))
                engine.store.save_discovery_idea(run_id, key, note=checked.note.model_dump(mode="json"),
                    status="checked", check_action_observed=observed)
                if not engine.store.get_run(run_id).state.get("first_note_at"):
                    engine.checkpoint(run_id, first_note_at=utc_now())
                merge_updates(engine, run_id, checked.field_updates)
                publish(engine, run_id)
            reason = checked.note.reason if triage.action == "investigate" else triage.reason
        else:
            reason = sketch.reason
            engine.store.save_discovery_idea(run_id, key, status=sketch.action)
        run = engine.store.get_run(run_id)
        history = list(run.state.get("previous_directions", []))
        history.append({"draw_id": key, "direction": sketch.seed.title if sketch.seed else sketch.action,
                        "decision": (checked.note.decision if triage.action == "investigate" else triage.action) if sketch.seed else sketch.action,
                        "question": sketch.seed.question if sketch.seed else None,
                        "insight": sketch.seed.insight if sketch.seed else None, "reason": reason})
        completion = {key + "_done": True, "previous_directions": history}
        if sketch.next_search and sketch.action != "stop" and ordinal < campaign.max_draws and not run.state.get("survey_refresh_used"):
            completion.update(survey_refresh_used=True, survey_refresh_question=sketch.next_search)
        engine.checkpoint(run_id, **completion)
        if sketch.action == "stop":
            engine.complete(run_id, "ideator_stopped")
            publish(engine, run_id)
            return
    engine.complete(run_id, "discover_draws_finished_human_selection")
    publish(engine, run_id)


async def prestudy(engine, run_id):
    run = engine.store.get_run(run_id)
    task = "DEVELOP" if run.mode == "develop" else "PRESSURE"
    result = await engine.call(run_id, "prestudy", "scout", task, payload=run.state["idea_input"])
    result, observed = bound_check(result, engine.task_trace(run_id, "prestudy"))
    engine.checkpoint(run_id, prestudy_note=result.note.model_dump(mode="json"), check_action_observed=observed,
                      first_note_at=utc_now())
    engine.complete(run_id, "prestudy_finished_human_decision")
