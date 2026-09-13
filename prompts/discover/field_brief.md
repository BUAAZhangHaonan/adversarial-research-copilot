# 领域调查

{{ original_topic }}

{{ overview }}

## 已有路线

{{ research_lines }}

## 值得追问的问题

{{ openings }}

## 资料与阅读范围
{% for source in sources %}
### {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}

{{ source.finding }}

{{ source.relevance }}（{{ source.access_text }}）
{% endfor %}

## 尚未查清

{{ search_limits }}
