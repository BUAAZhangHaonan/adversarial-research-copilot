# 提示词、调用与证据追踪

运行：{{ run_id }}

此索引只链接已保存的调用材料。原始模型消息只用于本地审计，不构成论文证据。

[完整检索命中审计](SEARCH_SOURCES.md)。检索命中、已登记的工作证据与报告正式引文分别保留，不相互等同。

{% for task in tasks %}
## {{ task.id }} — {{ task.status }}

{{ task.identity }}

输入证据：{{ task.evidence }}

{% for artifact in task.artifacts %}
- [{{ artifact.label }}]({{ artifact.path }})
{% endfor %}
{% endfor %}

## 证据关系

{% for evidence in evidence_records %}
- {{ evidence.id }} → {{ evidence.source_id }}：{{ evidence.claim }}；方向：{{ evidence.relation }}；条件：{{ evidence.conditions }}；定位：{{ evidence.locator }}；核验状态：{{ evidence.verification }}。
{% endfor %}
