# {{ report_title }}

{{ executive_summary }}

## 值得继续的研究卡

{% for card in main_cards %}
### {{ card.title }}

{{ card.decision_paragraph }}

{{ card.insight_paragraph }}

{{ card.motivation_paragraph }}

{{ card.knowledge_gain_paragraph }}

{{ card.main_risk_paragraph }}

[查看研究卡详情]({{ card.relative_path }})
{% else %}
本次没有形成可进入主报告的研究卡。候选的具体判断见下方；不能据此断言整个领域没有研究空间。
{% endfor %}

{% if leads %}
## 待补证线索

{% for lead in leads %}
### {{ lead.title }}

{{ lead.decision_paragraph }}

核心认识：{{ lead.insight_paragraph }}

{{ lead.knowledge_gain_paragraph }}

主要未决风险：{{ lead.main_risk_paragraph }}

#### 缺失前提与下一步

{{ lead.missing_prerequisite_paragraph }}

{{ lead.reopening_action_paragraph }}
{% endfor %}
{% endif %}

{% if rejected %}
## 本次未推荐的候选

{% for card in rejected %}
### [{{ card.title }}]({{ card.path }})

{{ card.reason }}

{% for correction in card.corrections %}
{{ correction }}
{% endfor %}

{% for defect in card.defects %}
当前必要缺陷（{{ defect.location }}）：{{ defect.reason }} 必要修改：{{ defect.required_change }}
{% endfor %}
{% endfor %}
{% endif %}

{% if scope_changes %}
## 尚未推进的转向建议

{% for change in scope_changes %}
{{ change.summary }}

{{ change.original_evidence_audit }}

该建议已冻结，原卡没有被覆盖，也没有继续进入新方向的后续流程。
{% endfor %}
{% endif %}

## 调查范围与当前状态

{{ scope_paragraph }}

{{ execution_status_paragraph }}

## 费用和后续动作

{{ cost_paragraph }}

{{ next_step_paragraph }}

## 正式来源

以下来源服务于卡片、争点或当前结论；搜索命中不自动成为引用。

{% for source in sources %}
- [{{ source.id }}：{{ source.title }}]({{ source.url }})
{% endfor %}

[完整调用与证据记录](PROMPT_TRACE_INDEX.md) · [检索命中审计](SEARCH_SOURCES.md)
