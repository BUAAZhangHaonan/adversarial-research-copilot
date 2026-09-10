# {{ title }}

## 阶段摘要

{{ stage_summary }}

## 研究总览

{{ overview }}

## 候选与原始判断

{% for candidate in candidates %}
- [{{ candidate.title }}]({{ candidate.path }})：{{ candidate.decision }}。
{% endfor %}
{% if not candidates %}
本阶段没有已保存的候选灵感。
{% endif %}

## 引用来源

{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}（{{ source.id }}）。
{% endfor %}

## 执行与原稿

{{ execution_status }}

正文经过最终语言整理，研究对象与判断仍以保存记录为准；润色不构成新的研究验证。

[查看原始技术报告](TECHNICAL_REPORT.md) · [费用](COST_REPORT.md) · [任务记录](PROMPT_TRACE_INDEX.md) · [共享调查](FIELD_BRIEF.md)
