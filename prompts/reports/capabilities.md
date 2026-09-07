# 缺失的 MCP 能力

运行：{{ run_id }}

{% for request in requests %}
## {{ request.blocked_question }}

{{ request.details }}
{% endfor %}

这里只记录当前工作所需能力，没有安装工具或修改外部服务。

## 改进需求的处理边界

本清单也包括已有工具和工作流的限制改进。pending_user_review 表示待用户评估，
reviewed 表示已记录评估。用户决定是否实施；模板不会自动创建任务或引入外部评估依赖。
历史开发评估保留原标签和评估者，不能据此推定正式运行仍依赖开发阶段评估。
