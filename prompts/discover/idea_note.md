# {{ title }}

{{ status_text }}。这是一份预研建议，由人决定是否继续。

{% if current %}
**当前核心想法**

{{ current.core_insight }}

**已有方法为何仍不足**

{{ current.why_existing_insufficient }}

**决定性未知**

{{ current.decisive_unknown }}

{% if withdrawn_premises %}
**已撤回前提**

{{ withdrawn_premises }}
{% endif %}
{% endif %}
{% if relation %}
候选关系：{{ relation }}
{% endif %}
{% if material_basis %}
{{ material_basis }}
{% endif %}

{% if changes %}
## 本次实质调整

{{ changes }}
{% endif %}

**初始灵感（预研前，可能已被上述调整修正）**

{% if current and current.core_insight == insight %}核心认识未变，见上方当前核心想法。{% else %}{{ insight }}{% endif %}

**初始动机（预研前）**

{{ why_it_matters }}

**文献已经做到哪里，这里还差什么**

{{ literature_paragraph }}

**大致能不能做**

{{ feasibility_paragraph }}

{{ resource_paragraph }}

{% if main_risk %}
**最可能错在哪里**

{{ main_risk }}
{% endif %}

{{ limits_paragraph }}

{% if next_question %}
**先讨论这个问题**

{{ next_question }}
{% endif %}

## 关键来源

{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}：{{ source.relevance }}（{{ source.access_text }}）。
{% endfor %}

{{ provenance_line }}
