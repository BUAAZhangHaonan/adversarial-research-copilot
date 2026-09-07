## 未保留的卡与未完成事项

{% if pending_cards %}
### 当前卡与未完成判断

{% for card in pending_cards %}
{{ card.title }}：{{ card.decision }}

[查看当前研究卡]({{ card.path }})
{% endfor %}
{% endif %}

{% for card in rejected %}
### {{ card.title }}

{{ card.decision }}

重开条件：{{ card.reopen }}

[查看研究卡详情]({{ card.path }})
{% endfor %}

{% for task in pending_tasks %}
- {{ task.id }}：{{ task.status }}；{{ task.reason }}
{% endfor %}

## 争点记录

{% for issue in issues %}
- {{ issue.id }}（{{ issue.status }}）：{{ issue.content }}。解除标准：{{ issue.criterion }}。本轮变化：{{ issue.change }}。
{% else %}
当前没有登记争点；这不等同于研究假设已被验证。
{% endfor %}

[查看调用与证据追踪](PROMPT_TRACE_INDEX.md) · [查看费用记录](COST_REPORT.md)
