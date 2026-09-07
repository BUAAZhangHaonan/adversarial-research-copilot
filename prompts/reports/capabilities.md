# 缺失的 MCP 能力

运行：{{ run_id }}

{% for request in requests %}
## {{ request.blocked_question }}

{{ request.details }}
{% endfor %}

这里只记录当前工作所需能力，没有安装工具或修改外部服务。
