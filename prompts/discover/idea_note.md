# {{ title }}

{{ status_text }}。这是一份预研建议，由人决定是否继续。

**核心想法**

{{ insight }}

**为什么值得看**

{{ why_it_matters }}

**文献已经做到哪里，这里还差什么**

{{ literature_paragraph }}

**大致能不能做**

{{ feasibility_paragraph }}

{{ resource_paragraph }}

**最可能错在哪里**

{{ main_risk }}

{{ limits_paragraph }}

**先讨论这个问题**

{{ next_question }}

{% if changes %}
## 本次实质调整

{{ changes }}
{% endif %}

## 关键来源

{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}：{{ source.relevance }}（{{ source.access_text }}）。
{% endfor %}

{{ provenance_line }}
