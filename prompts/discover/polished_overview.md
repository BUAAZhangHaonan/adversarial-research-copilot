# {{ title }}

{{ stage_summary }}

{% if overview %}
{{ overview }}
{% endif %}

{% if candidates %}
## {% if candidates | length == 1 %}想法详情{% else %}本次想法{% endif %}
{% for candidate in candidates %}
- [{{ candidate.title }}]({{ candidate.path }})：{{ candidate.decision }}。
{% endfor %}
{% else %}
本阶段没有已保存的候选灵感。
{% endif %}

{% if sources %}
## 关键来源
{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}
{% endfor %}
{% endif %}

{{ execution_status }}

[预研记录](TECHNICAL_REPORT.md) · [文献调查](FIELD_BRIEF.md) · [费用](COST_REPORT.md) · [运行记录](PROMPT_TRACE_INDEX.md)
