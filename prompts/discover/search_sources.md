# 检索命中审计

检索命中不表示相关、已读或支持当前结论。正式引用见具体预研卡；领域资料见共享调查。

{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}（{{ source.id }}）
{% endfor %}
