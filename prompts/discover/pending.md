# {{ title }}

{{ status_text }}。

{{ insight }}

{{ question }}

{{ why_it_matters }}

## 目前的判断与待查问题

{{ difference }}

{{ reason }}

{{ unknown }}

{{ questions }}

## 启发来源
{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}：{{ source.relevance }}（{{ source.access_text }}）
{% endfor %}

{{ provenance_line }}
