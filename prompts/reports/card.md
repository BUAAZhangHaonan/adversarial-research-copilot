# {{ title }}

{{ decision_paragraph }}

## 核心认识与研究价值

{{ insight_paragraph }}

{{ motivation_paragraph }}

{{ knowledge_gain_paragraph }}

## 与最接近工作的区别

{{ nearest_work_paragraph }}

## 核心判断和另一种解释

{{ hypothesis_paragraph }}

{{ alternative_paragraph }}

## 最小验证怎么做

{{ test_paragraph }}

{{ result_interpretation_paragraph }}

## 需要多少资源

{{ resource_paragraph }}

## 最可能失败在哪里

{{ risks_paragraph }}

{{ unresolved_paragraph }}

## 当前版本与下一步

{{ version_paragraph }}

{{ next_step_paragraph }}

## 审查记录与引用依据

{{ review_paragraph }}

{{ bindings_paragraph }}

出处可定位只确认摘录存在，不代表摘录在当前设置下支持主张。保留判断仍需要事实归属与推理审查。

{% for evidence in evidence_notes %}
### {{ evidence.id }} → {{ evidence.source_id }}

原文摘录：{{ evidence.excerpt }}

定位：{{ evidence.locator }}；关系：{{ evidence.relation }}。

适用条件：{{ evidence.conditions }}

支持关系说明（待按内容审查）：{{ evidence.support_explanation }}
{% endfor %}

## 正式来源

{% for source in sources %}
- [{{ source.id }}：{{ source.title }}]({{ source.url }})
{% endfor %}

[完整调用与证据记录](../../PROMPT_TRACE_INDEX.md) · [检索命中审计](../../SEARCH_SOURCES.md)
