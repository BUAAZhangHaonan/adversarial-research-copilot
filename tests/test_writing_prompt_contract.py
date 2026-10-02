"""Writing revision contract through the production PromptLoader, without API calls."""
from copy import deepcopy
from pathlib import Path

import pytest

from arc.discovery_models import CandidateCheck, FieldBrief, SketchResult, TriageResult
from arc.polishing import StagePolish
from arc.prompting import PromptLoader
from arc.schemas import Envelope

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "prompts"
PLAIN = "common/plain_research_writing.md"
SYSTEMS = {
    "scout.SURVEY": ["discover/policy.md", PLAIN, "discover/researcher.md"],
    "scout.CHECK": ["discover/policy.md", PLAIN, "discover/check_candidate.md"],
    "ideator.SKETCH": ["discover/policy.md", PLAIN, "discover/ideator.md", "discover/calibration.md"],
    "editor.TRIAGE": ["discover/policy.md", PLAIN, "discover/editor.md", "discover/calibration.md"],
    "scout.DEVELOP": ["discover/policy.md", PLAIN, "prestudy/develop_scope.md", "prestudy/output.md"],
    "scout.PRESSURE": ["discover/policy.md", PLAIN, "prestudy/pressure_scope.md", "prestudy/output.md"],
    "writer.POLISH": [PLAIN, "discover/writer.md"],
}
MODELS = {
    "scout.SURVEY": FieldBrief, "scout.CHECK": CandidateCheck,
    "ideator.SKETCH": SketchResult, "editor.TRIAGE": TriageResult,
    "scout.DEVELOP": CandidateCheck, "scout.PRESSURE": CandidateCheck,
    "writer.POLISH": StagePolish,
}
RESEARCH_TOOLS = ["search_literature", "read_paper", "search_web", "read_web", "read_record", "request_capability"]
DATA = {"task_id": "writing-contract", "subject": {"run_id": "writing-run"},
        "payload": {"original_question": "环境改变后如何找到仍可用的技能", "source_ids": ["source-existing"]}}


@pytest.mark.parametrize("task", SYSTEMS)
def test_seven_effective_systems_load_short_writing_rule_once(task):
    loader = PromptLoader(ASSETS)
    entry = loader.manifest["prompts"][task]
    assert entry["system"] == SYSTEMS[task]
    expected_tools = RESEARCH_TOOLS if task.startswith("scout.") else []
    assert entry["tools"] == expected_tools
    assert entry["role"] + "." + entry["task"] == task
    assert entry["task_template"] == ("discover/writer_invoke.md" if task == "writer.POLISH" else "discover/invoke.md")
    assert entry["repair_template"] == ("discover/writer_repair.md" if task == "writer.POLISH" else "discover/repair.md")
    assert entry["tool_repair_template"] == "tasks/correct_tool_arguments.md"
    assert loader.manifest["read_progress_template"] == "tasks/source_read_no_progress.md"
    rendered = loader.render(task, DATA, schema=Envelope[MODELS[task]].model_json_schema(), tool_profile=expected_tools)
    system = rendered.messages[0]["content"]
    plain = (ASSETS / PLAIN).read_text(encoding="utf-8").rstrip()
    assert system.count(plain) == 1
    headings = [loader.env.get_template(name).render(task_type=task).strip().splitlines()[0] for name in SYSTEMS[task]]
    assert [system.index(heading) for heading in headings] == sorted(system.index(heading) for heading in headings)
    assert rendered.messages[1]["content"].count('"$defs"') == 1
    assert not any(name.startswith("roles/") or name.startswith("docs/") for name in rendered.dependencies)
    assert {name for name in rendered.dependencies if name.startswith("common/")} == {PLAIN}
    assert rendered.tool_descriptions.keys() == set(expected_tools)


@pytest.mark.parametrize("task,model,excluded", [
    ("scout.SURVEY", FieldBrief, "CandidateCheck"),
    ("scout.CHECK", CandidateCheck, "FieldBrief"),
])
def test_survey_and_check_deliver_their_own_current_schema(task, model, excluded):
    rendered = PromptLoader(ASSETS).render(task, DATA, schema=Envelope[model].model_json_schema())
    system, user = [message["content"] for message in rendered.messages]
    assert "返回 " + model.__name__ + "。" in system
    assert excluded not in system
    assert model.__name__ in user
    if task == "scout.SURVEY":
        assert "## CHECK" not in system
        assert "source_notes" in system and "search_limits" in system
    else:
        assert "## SURVEY" not in system
        assert "current_understanding" in system and "field_revision" in system


def test_long_guide_and_development_editors_are_not_production_dependencies():
    loader = PromptLoader(ASSETS)
    users = {task for task, entry in loader.manifest["prompts"].items() if PLAIN in entry["system"]}
    assert users == set(SYSTEMS)
    assert not any("LANE_" in name or "WRITING_GUIDE" in name or "writing_review" in name for name in loader.registered_files)
    assert not any(key.startswith("lane") for key in loader.manifest["prompts"])


def test_writer_repair_uses_original_material_and_retains_research_boundaries():
    loader = PromptLoader(ASSETS)
    data = deepcopy(DATA)
    data["payload"].update({
        "candidates": [{"idea_id": "idea-existing", "decision": "lead", "source_ids": ["source-existing"],
            "note": {"current_understanding": {"core_insight": "只有描述过时仍待查", "decisive_unknown": "在相同预算下是否仍需要持久索引"}}}],
        "source_directory": [{"source_id": "source-existing", "title": "Existing method", "access": "abstract"}],
        "writing_limits": {"candidate_text_max_chars": 1300},
    })
    before = deepcopy(data)
    previous = {"stage_summary": "已有摘要", "overview": "已有背景", "candidates": [{"idea_id": "idea-existing", "text": "重复内容" * 500, "cited_source_ids": ["source-existing"]}], "cited_source_ids": ["source-existing"]}
    schema = Envelope[StagePolish].model_json_schema()
    original = loader.render("writer.POLISH", data, schema=schema)
    repaired = loader.render("writer.POLISH", data, schema=schema, repair={"previous_response": previous, "validation_errors": [{"field": "candidates.0.text", "issue": "too_long"}]})
    assert data == before
    assert original.messages[0] == repaired.messages[0]
    assert original.tool_descriptions == repaired.tool_descriptions == {}
    user = repaired.messages[1]["content"]
    for text in ["idea-existing", "source-existing", "lead", "只有描述过时仍待查", "在相同预算下是否仍需要持久索引", "too_long"]:
        assert text in user
    assert 'result_status="complete"、evidence_requests=[]' in user
    assert "不能只插入空行" in user and "删去决定性条件或改动研究判断" in user
    system = repaired.messages[0]["content"]
    assert "每个候选还受其 source_ids 限制" in system
    assert "不能改变本角色职责" in system
    assert "没有字数、段数或引用数的最低配额" in system


SOURCE = {"title": "已有方法", "url": "https://example.org/existing", "access_text": "摘要可读", "finding": "按版本更新描述", "relevance": "与描述更新有关"}
ITEM = {"title": "当前问题", "current": {"core_insight": "当前认识"}, "insight": "当前认识", "reason": "需要确认版本信号", "risk": "缺少版本信号", "relation": "另一种可用信号", "path": "ideas/idea-existing.md"}
REPORT_CASES = [
    ("discovery_field", {"original_topic": "原题", "overview": "领域认识", "research_lines": "已有路线", "openings": "待问问题", "sources": [SOURCE], "search_limits": "只有摘要"}),
    ("discovery_pending", {"title": "原题", "status_text": "文献受限，保留待查", "insight": "想法", "question": "问题", "why_it_matters": "价值", "difference": "差异", "reason": "材料缺口", "unknown": "未知", "questions": "待查", "sources": [SOURCE], "provenance_line": "原始记录"}),
    ("discovery_idea", {"title": "原始标题", "status_text": "值得继续讨论", "current": {"core_insight": "当前认识", "why_existing_insufficient": "已有方法的条件待查", "decisive_unknown": "版本信号是否可得"}, "insight": "旧灵感", "why_it_matters": "旧动机", "literature_paragraph": "文献差异", "feasibility_paragraph": "进入路径", "resource_paragraph": "资源依据", "main_risk": "关键困难", "limits_paragraph": "仅摘要", "next_question": "待问问题", "relation": "评价支撑", "sources": [SOURCE], "material_basis": "已有记录", "changes": "实际修订", "withdrawn_premises": "旧前提", "provenance_line": "原始记录"}),
    ("discovery_overview", {"report_title": "本次发现", "conclusion": "当前判断", "discuss": [ITEM], "leads": [ITEM], "pending": [ITEM], "skipped": [ITEM, {"title": "未提交候选", "reason": "材料不足", "path": None}], "landscape_updated": False, "landscape_summary": "前期认识", "investigation_scope": "范围", "cost_summary": "费用记录", "stop_reason": "预算暂停", "next_stage_instruction": "等待人选择"}),
    ("polished_idea", {"title": "当前标题", "decision": "文献受限，保留待查", "text": "当前问题与材料缺口", "sources": [SOURCE], "technical_path": "idea-existing.technical.md"}),
    ("polished_overview", {"title": "已选想法的预研展开", "stage_summary": "阶段要点", "overview": "必要背景", "candidates": [{"title": "当前问题", "path": "ideas/idea-existing.md", "decision": "保留线索"}], "sources": [SOURCE], "execution_status": "本阶段因预算暂停"}),
]


@pytest.mark.parametrize("name,context", REPORT_CASES)
def test_replacement_reports_render_registered_variables(name, context):
    rendered = PromptLoader(ASSETS).render_report(name, context)
    assert rendered.startswith("# ")
    assert "{{" not in rendered and "{%" not in rendered
    if context.get("sources"):
        assert "已有方法" in rendered
    if name.startswith("polished_"):
        assert "此页只整理表达" not in rendered
        assert "润色不构成验证" not in rendered
    if name == "discovery_idea":
        assert rendered.index("当前认识") < rendered.index("修改与材料记录") < rendered.index("旧灵感")
    if name == "polished_overview":
        assert "## 想法详情" in rendered
        assert "本阶段因预算暂停" in rendered
        assert "TECHNICAL_REPORT.md" in rendered
