# 缺失的 MCP 能力

运行：{{ run_id }}

{% for request in requests %}
## {{ request.blocked_question }}

{{ request.details }}
{% endfor %}

这里只记录当前工作所需能力，没有安装工具或修改外部服务。

## 改进需求的处理边界

本清单也包括已有工具和工作流的限制改进。pending_codex_review 表示待 CodeX 评估，
reviewed 表示已记录评估。评估建议不等于执行授权；用户支线模板不会自动创建任务。
