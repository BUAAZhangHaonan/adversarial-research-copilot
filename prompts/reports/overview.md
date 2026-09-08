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
本次没有形成可进入主报告的研究卡。具体原因见调查范围和未完成事项，不能据此断言整个领域没有研究空间。
{% endfor %}

{% if leads %}
## 待补证线索

{% for lead in leads %}
### {{ lead.title }}

{{ lead.missing_prerequisite_paragraph }}

{{ lead.reopening_action_paragraph }}
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
