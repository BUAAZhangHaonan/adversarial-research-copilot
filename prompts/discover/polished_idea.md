# {{ title }}

{{ decision }}。

{{ text }}

{% if sources %}
## 关键来源
{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}（{{ source.access_text }}）
{% endfor %}
{% endif %}

[详细预研记录]({{ technical_path }}) · [返回总览](../REPORT.md)
