# 共享领域调查

{{ original_topic }}

{{ overview }}

## 路线关系

{{ research_lines }}

## 开放切入点

{{ openings }}

## 关键材料与阅读边界

{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}：{{ source.finding }}。相关性：{{ source.relevance }}（{{ source.access_text }}）。
{% endfor %}

## 调查限制

{{ search_limits }}
