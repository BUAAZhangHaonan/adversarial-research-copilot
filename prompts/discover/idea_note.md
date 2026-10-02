# {{ title }}

{{ status_text }}。

{% if current %}
{{ current.core_insight }}

{{ current.why_existing_insufficient }}

当前最需要弄清：{{ current.decisive_unknown }}
{% else %}
{{ insight }}

{{ why_it_matters }}
{% endif %}

## 文献与进入路径

{{ literature_paragraph }}

{{ feasibility_paragraph }}

{% if main_risk %}{{ main_risk }}

{% endif %}{{ limits_paragraph }}

{% if next_question %}{{ next_question }}
{% endif %}

{% if relation %}与其他想法的关系：{{ relation }}
{% endif %}

## 关键来源
{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}：{{ source.relevance }}（{{ source.access_text }}）
{% endfor %}

## 修改与材料记录

{% if decision_reason is defined and decision_reason %}判断依据：{{ decision_reason }}

{% endif %}{{ resource_paragraph }}

{% if material_basis %}{{ material_basis }}

{% endif %}{% if changes %}{{ changes }}

{% endif %}{% if withdrawn_premises %}已撤回的前提：{{ withdrawn_premises }}

{% endif %}{% if current %}以下保留预研前的灵感与动机，当前判断见上文。

{% if insight != current.core_insight %}{{ insight }}{% else %}预研前后的核心认识相同。{% endif %}

{{ why_it_matters }}

{% endif %}{{ provenance_line }}
