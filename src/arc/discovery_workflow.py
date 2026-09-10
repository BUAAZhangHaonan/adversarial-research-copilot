"""Discover short ideas first; preserve paid task boundaries and human handoff."""
from __future__ import annotations
from .discovery_models import FieldBrief, CandidateCheck
from .schemas import utc_now


from .research_context import build_discovery_context as context, compact_idea_view, discovery_directions


def publish(engine, run_id):
    from .reports import render_run
    render_run(engine.store, run_id, engine.settings.data_dir.resolve() / "reports" / run_id)


async def finish_stage(engine, run_id, reason):
    """One cached editorial task after research; historical bundles stay historical."""
    if 'writer.POLISH' in engine.runtime.loader.manifest['prompts']:
        from .polishing import build_polish_payload
        await engine.call(run_id, 'polish', 'writer', 'POLISH',
                          payload=build_polish_payload(engine.store, run_id), tool_profile=[])
    engine.complete(run_id, reason)
    publish(engine, run_id)


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


def check_material_basis(trace, note, available_notes=()):
    if check_action_observed(trace, note):
        return "task_read"
    cited = {n.source_id for n in note.source_notes} | {w.source_id for w in note.nearest_work}
    usable = {n["source_id"] for n in available_notes
              if n.get("access") in {"abstract", "passage", "full_text", "code", "secondary"}
              and n.get("finding")}
    return "shared_notes" if cited & usable else "unverified"


def bound_check(result, trace, available_notes=()):
    observed = check_action_observed(trace, result.note)
    if check_material_basis(trace, result.note, available_notes) == "unverified":
        body = result.model_dump(mode="json")
        note = body["note"]
        note["limits"].append("本次任务未取得相关有效材料，输入中也没有可复用的相关阅读笔记；预研结论仍待核查。")
        if note["decision"] == "discuss": note["decision"] = "lead"
        result = CandidateCheck.model_validate(body)
    return result, observed


def merge_updates(engine, run_id, updates, revision=None):
    """Replace current readings/narrative; retain the previous brief as history."""
    run = engine.store.get_run(run_id)
    old = run.state["field_brief"]
    brief = dict(old)
    grouped = {}
    for update in updates:
        value = update.model_dump(mode="json")
        values = grouped.setdefault(value["source_id"], [])
        if value not in values: values.append(value)
    if grouped:
        brief["source_notes"] = [note for note in old["source_notes"] if note["source_id"] not in grouped]
        brief["source_notes"].extend(note for values in grouped.values() for note in values)
    if revision is not None:
        brief.update(revision.model_dump(mode="json", exclude_none=True))
    brief = FieldBrief.model_validate(brief).model_dump(mode="json")
    if brief != old:
        history = list(run.state.get("field_brief_history", []))
        history.append({"version": run.state.get("brief_version", 1), "field_brief": old})
        engine.checkpoint(run_id, field_brief=brief, field_brief_history=history,
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
                await finish_stage(engine, run_id, "ideator_stopped")
                return
            continue
        if run.state.get("survey_refresh_used") and not run.state.get("survey_refresh_applied"):
            brief = await engine.call(run_id, "survey.refresh", "scout", "SURVEY", payload={
                **context(engine, run_id), "refresh_question": run.state["survey_refresh_question"]})
            engine.checkpoint(run_id, field_brief=brief.model_dump(mode="json"),
                              brief_version=run.state.get("brief_version", 1) + 1, survey_refresh_applied=True)
            run = engine.store.get_run(run_id)
        payload = {**context(engine, run_id, task="SKETCH", exclude_draw_id=key), "draw_id": key,
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
        shared_followup_handled = False
        if sketch.action == "submit":
            seed = sketch.seed.model_dump(mode="json")
            archive = engine.store.lookup_archive(sketch.seed.question, limit=4)
            previous = [compact_idea_view(x) for x in engine.store.lookup_discovery_ideas(
                sketch.seed.question, exclude_run_id=run_id, limit=4)]
            triage = await engine.call(run_id, key + ".triage", "editor", "TRIAGE", payload={
                **context(engine, run_id, task="TRIAGE", seed=seed, exclude_draw_id=key),
                "idea_id": record["idea_id"], "seed": seed, "require_candidate_relation": True,
                "local_archive": archive, "previous_ideas": previous})
            engine.store.save_discovery_idea(run_id, key, triage=triage.model_dump(mode="json"),
                status="pending" if triage.action == "investigate" else triage.action)
            publish(engine, run_id)
            if triage.action == "investigate":
                checked = await engine.call(run_id, key + ".check", "scout", "CHECK", payload={
                    **context(engine, run_id, task="CHECK", exclude_draw_id=key),
                    "idea_id": record["idea_id"], "seed": seed, "require_current_understanding": True,
                    "triage": triage.model_dump(mode="json"),
                    **({"shared_followup_question": sketch.next_search} if sketch.next_search else {})})
                # Cached and resumed tasks retain their original input; do not infer
                # that an older CHECK received this handoff from the newly constructed payload.
                accepted_input = engine.store.get_run(run_id).state.get("task_inputs", {}).get(
                    key + ".check", {}).get("payload", {})
                shared_followup_handled = bool(sketch.next_search) and (
                    accepted_input.get("shared_followup_question") == sketch.next_search)
                trace = engine.task_trace(run_id, key + ".check")
                supplied = engine.store.get_run(run_id).state["field_brief"].get("source_notes", [])
                basis = check_material_basis(trace, checked.note, supplied)
                checked, observed = bound_check(checked, trace, supplied)
                engine.store.save_discovery_idea(run_id, key, note=checked.note.model_dump(mode="json"),
                    status="checked", check_action_observed=observed, check_material_basis=basis)
                if not engine.store.get_run(run_id).state.get("first_note_at"):
                    engine.checkpoint(run_id, first_note_at=utc_now())
                merge_updates(engine, run_id, [*checked.note.source_notes, *checked.field_updates], checked.field_revision)
                publish(engine, run_id)
            reason = checked.note.reason if triage.action == "investigate" else triage.reason
        else:
            reason = sketch.reason
            engine.store.save_discovery_idea(run_id, key, status=sketch.action)
        run = engine.store.get_run(run_id)
        history = discovery_directions(engine, run_id)
        completion = {key + "_done": True, "previous_directions": history}
        if (sketch.next_search and not shared_followup_handled and sketch.action != "stop"
                and ordinal < campaign.max_draws and not run.state.get("survey_refresh_used")):
            completion.update(survey_refresh_used=True, survey_refresh_question=sketch.next_search)
        engine.checkpoint(run_id, **completion)
        if sketch.action == "stop":
            await finish_stage(engine, run_id, "ideator_stopped")
            return
    await finish_stage(engine, run_id, "discover_draws_finished_human_selection")


async def prestudy(engine, run_id):
    run = engine.store.get_run(run_id)
    task = "DEVELOP" if run.mode == "develop" else "PRESSURE"
    result = await engine.call(run_id, "prestudy", "scout", task, payload={**run.state["idea_input"], "require_current_understanding": True})
    trace = engine.task_trace(run_id, "prestudy")
    supplied = [*(run.state["idea_input"].get("field_brief") or {}).get("source_notes", []),
                *(run.state["idea_input"].get("latest_note") or {}).get("source_notes", [])]
    basis = check_material_basis(trace, result.note, supplied)
    result, observed = bound_check(result, trace, supplied)
    engine.checkpoint(run_id, prestudy_note=result.note.model_dump(mode="json"), check_action_observed=observed,
                      check_material_basis=basis,
                      first_note_at=utc_now())
    if not engine.store.get_run(run_id).state.get("field_brief"):
        inherited_brief = run.state["idea_input"].get("field_brief")
        if inherited_brief:
            engine.checkpoint(run_id, field_brief=inherited_brief, brief_version=1)
    if engine.store.get_run(run_id).state.get("field_brief"):
        merge_updates(engine, run_id, [*result.note.source_notes, *result.field_updates], result.field_revision)
    await finish_stage(engine, run_id, "prestudy_finished_human_decision")
