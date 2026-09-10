# {{ title }}

{{ decision }}。这是原预研记录的判断，由人决定是否继续。

{{ text }}

## 关键来源

{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}（{{ source.access_text }}）。
{% endfor %}

{% if original_title %}
原研究标题（历史）：{{ original_title }}。
{% endif %}

[查看本候选原始技术稿]({{ technical_path }}) · [返回阶段总览](../REPORT.md)

{{ provenance }}
