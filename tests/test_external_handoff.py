"""Offline contract tests. The normal workflow, writer, store and reports run against an isolated DB."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from arc.cli import app, services
from arc.config import Settings
from arc.external_idea import SelectedIdea
from arc.handoff import handoff_lock, import_selected, recover_registration
from arc.handoff_result import export_result
from arc.polishing import build_polish_payload
from arc.reports import render_run
from arc.schemas import SourceRecord
from arc.store import StateError
from arc.workflows import WorkflowEngine
from tests.test_discovery_workflow import ScriptedRuntime, checked


def payload():
    return {"schema_version":"radar.arc.selected-idea.v1","handoff_id":"sample-develop",
        "origin":{"system":"ScholarRadar","direction_id":"d7","snapshot_id":"s3","profile_id":"p2"},
        "request":{"stage":"develop","focus":"区分证据进入的时机与难度。","boundaries":["只预研"]},
        "proposal":{"title":"补充证据的时机","question":"信息补充在作出决定前是否有影响？",
        "hypothesis":"时机可能改变选择","expected_value":"减少无效信息补充",
        "claimed_difference":"将时机与覆盖分开比较","decisive_unknown":"难度是否解释观察"},
        "sources":[{"external_source_id":"E1","work_id":"W1","revision_id":"v17","evidence_ids":["E1"],
        "title":"A controlled timing study","url":"https://example.org/timing","version":"v2","access":"passage",
        "content":"Matched conditions used the same examples.","start_char":780,"total_chars":4800}],
        "source_notes":[{"external_source_id":"E1","finding":"两组使用相同样本。","relevance":"可以比较时机。",
                         "access":"passage","limits":"仅含一个结果段。"}],
        "assets":["冻结的评估集"],"profile":{"goals":["理解模型选择"]},"resource_conditions":{"GPU":None}}


def test_import_is_idempotent_immutable_and_mapped(tmp_path):
    settings=Settings(data_dir=tmp_path)
    raw=payload(); request=SelectedIdea.model_validate(raw)
    with ThreadPoolExecutor(3) as pool:
        values=list(pool.map(lambda _:import_selected(settings,request),range(3)))
    record=values[0]; assert all(v["run_id"]==record["run_id"] and v["idea_id"]==record["idea_id"] for v in values)
    store,ledger=services(settings); result=export_result(store,ledger,request.handoff_id)
    assert result["execution_status"]=="prepared" and result["cost"]["call_count"]==0
    assert result["origin"]==raw["origin"] and result["idea_id"]!=raw["origin"]["direction_id"]
    native=store.get_run(result["run_id"])
    assert native.campaign_id is None and store.list_discovery_ideas()==[]
    m=record["source_mapping"][0]; src=store.get_source(m["source_id"])
    assert src.source_id!="E1" and src.version=="v2" and not src.content_complete
    assert (src.content_start_char,src.content_total_chars)==(780,4800)
    assert store.read_artifact(src.content_path)==raw["sources"][0]["content"]
    assert native.state["idea_input"]["seed"]["source_ids"]==[src.source_id]
    assert native.state["idea_input"]["research_profile"]==raw["profile"]
    assert store.get_record(record["idea_id"])["seed"]["question"]==raw["proposal"]["question"]
    raw["request"]["focus"]="另一个比较"
    with pytest.raises(StateError,match="immutable"): import_selected(settings,SelectedIdea.model_validate(raw))
    another=payload();another["handoff_id"]="another-idea"
    assert import_selected(settings,SelectedIdea.model_validate(another))["idea_id"]!=record["idea_id"]


def test_inconsistent_extents_and_unknown_notes_are_rejected():
    raw=payload(); raw["sources"][0]["access"]="full_text"
    with pytest.raises(ValidationError): SelectedIdea.model_validate(raw)
    raw=payload();raw["source_notes"][0]["external_source_id"]="missing"
    with pytest.raises(ValidationError): SelectedIdea.model_validate(raw)
    raw=payload();raw["source_notes"][0]["access"]="full_text"
    with pytest.raises(ValidationError): SelectedIdea.model_validate(raw)


@pytest.mark.asyncio
async def test_two_real_stage_paths_render_and_export_later_source_and_draft(tmp_path):
    settings=Settings(data_dir=tmp_path)
    raw=payload()
    record=import_selected(settings,SelectedIdea.model_validate(raw))
    store,ledger=services(settings)
    new=store.register_source(SourceRecord(title="另一份近邻结果",url="https://example.org/neighbor",
        version="experiment-v1",source_type="paper",content_origin="original",access_status="retrieved",
        content_complete=False,content_total_chars=4000,content_start_char=300),content="A controlled comparator was reported.")
    sid=record["source_mapping"][0]["source_id"]
    imported=record["stage_input"]["field_brief"]["source_notes"][0]
    seed=record["stage_input"]["seed"]
    research=checked(seed,imported)
    additional={"source_id":new.source_id,"finding":"近邻报告了匹配对照。","relevance":"区分简单解释。",
                "access":"passage","limits":"已读结果段。"}
    research["note"]["source_notes"].append(additional)
    research["note"]["current_understanding"]={"core_insight":"两种解释可以用相同样本区分。",
        "illustrative_example":None,"invalidated_premises":[],"decisive_unknown":"两种时机的差异是否保留？","why_existing_insufficient":"还缺时机对照。"}
    prose="先固定相同的材料，再比较信息到达的时机。"
    technical="使用匹配对照，并单独检查任务难度。"
    polished={"stage_summary":"比较进入决策的时机。","overview":"两份材料提供了一个可核对的对照起点。",
        "candidates":[{"idea_id":record["idea_id"],"text":prose,"cited_source_ids":[sid,new.source_id],
                       "technical_analysis":technical}],"cited_source_ids":[new.source_id]}
    runtime=ScriptedRuntime({"prestudy":research,"polish":polished},include_polish=True)
    result=await WorkflowEngine(store,runtime,settings).execute(record["run_id"])
    assert result.status=="COMPLETED" and result.assessment is None
    out=export_result(store,ledger,raw["handoff_id"])
    assert out["research_decision"]=="discuss" and out["current_understanding"]==research["note"]["current_understanding"]
    assert out["presentation"]["candidates"][0]["text"]==prose
    assert out["presentation"]["candidates"][0]["technical_analysis"]==technical
    assert new.source_id in out["cited_source_ids"]
    retrieved=next(x for x in out["source_directory"] if x["source_id"]==new.source_id)
    assert (retrieved["url"],retrieved["version"],retrieved["origin"],retrieved["reading_level"])==(
        new.url,"experiment-v1","arc_stage","passage")
    writer_input=build_polish_payload(store,record["run_id"])
    assert writer_input["candidates"][0]["idea_id"]==record["idea_id"]
    assert writer_input["stage_focus"]==raw["request"]["focus"]
    follow=deepcopy(raw);follow.update(handoff_id="sample-run",idea_id=record["idea_id"])
    follow["request"]={"stage":"run","focus":"这一对照能否排除难度解释？","boundaries":["只预研"]}
    next_stage=import_selected(settings,SelectedIdea.model_validate(follow))
    assert (next_stage["idea_id"],next_stage["stage_input"]["latest_note_origin"]["run_id"])==(record["idea_id"],record["run_id"])
    assert next_stage["run_id"]!=record["run_id"] and next_stage["stage_input"]["latest_note"]["decision"]=="discuss"
    second=ScriptedRuntime({"prestudy":research})
    final=await WorkflowEngine(store,second,settings).execute(next_stage["run_id"])
    assert final.mode=="run" and final.status=="COMPLETED"
    state=dict(final.state,polish_failure={"reason":"INVALID_OUTPUT_AFTER_REPAIR"})
    store.update_run(final.run_id,state=state)
    render_run(store,final.run_id,tmp_path/"reports"/final.run_id)
    draft=export_result(store,ledger,follow["handoff_id"])
    assert draft["presentation_status"]=="draft" and draft["draft"]["next_question"]==research["note"]["next_question"]
    assert draft["draft_text"] and draft["polish_failure"]["reason"]=="INVALID_OUTPUT_AFTER_REPAIR"
    assert new.source_id in {x["source_id"] for x in draft["source_directory"]}
    assert [t for _,_,t in second.calls]==["PRESSURE"]


def test_status_recovers_interrupted_registration_and_busy_executor(tmp_path):
    settings=Settings(data_dir=tmp_path);seed=SelectedIdea.model_validate(payload())
    body=import_selected(settings,seed); store,ledger=services(settings)
    # Model an interruption after persisting the immutable handoff and creating the budget.
    with store._transaction() as db:
        db.execute("DELETE FROM runs WHERE id=?",(body["run_id"],))
    recover_registration(store,seed.handoff_id)
    assert store.get_run(body["run_id"]).state["idea_input"]["idea_id"]==body["idea_id"]
    root=["--data-dir",str(tmp_path),"handoff"]
    cli=CliRunner()
    with handoff_lock(store,seed.handoff_id):
        with store._transaction() as db:
            db.execute("INSERT INTO handoff_executions VALUES(?,?)",(seed.handoff_id,"sample-start"))
        # A repeated POST can resolve its IDs even while a different process executes.
        again=cli.invoke(app,[*root,"import"],input=json.dumps(payload()))
        check=cli.invoke(app,[*root,"execute",seed.handoff_id])
        assert again.exit_code==0 and json.loads(again.stdout)["run_id"]==body["run_id"]
        assert check.exit_code==0 and json.loads(check.stdout)["execution_status"]=="running"
    assert ledger.summary(body["run_id"])["call_count"]==0


def test_unknown_or_conflicting_handoffs_do_not_create_another_account(tmp_path):
    root=["--data-dir",str(tmp_path),"handoff"]
    runner=CliRunner()
    unknown=runner.invoke(app,[*root,"result","unknown"])
    assert unknown.exit_code==3 and json.loads(unknown.stdout)["execution_status"]=="not_found"
    raw=payload()
    first=runner.invoke(app,[*root,"import"],input=json.dumps(raw))
    assert first.exit_code==0
    raw["request"]["focus"]="另一个研究问题"
    conflict=runner.invoke(app,[*root,"import"],input=json.dumps(raw))
    assert conflict.exit_code==2
    assert json.loads(conflict.stdout)["error"]["code"]=="handoff_id_reused_for_different_immutable_input"
    assert "另一个研究问题" not in conflict.stdout
