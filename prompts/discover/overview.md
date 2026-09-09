# {{ report_title }}

{{ conclusion }}

{{ landscape_summary }}

{% for item in discuss %}
## {{ item.title }}

{{ item.insight }}

{{ item.reason }}

主要风险：{{ item.risk }}

[阅读预研卡]({{ item.path }})
{% endfor %}

{% if leads %}
## 还值得留意的线索
{% for item in leads %}
**{{ item.title }}**：{{ item.insight }}

待查：{{ item.reason }}

[阅读线索]({{ item.path }})
{% endfor %}
{% endif %}

{% if pending %}
## 待预研
{% for item in pending %}
**{{ item.title }}**：{{ item.insight }}

{{ item.reason }}。尚未完成预研，不能当作推荐。

[查看已保存灵感]({{ item.path }})
{% endfor %}
{% endif %}

{% if skipped %}
## 本次没有继续的方向
{% for item in skipped %}
- {{ item.title }}：{{ item.reason }}{% if item.path %}（[查看记录]({{ item.path }})）{% endif %}
{% endfor %}
{% endif %}

## 调查与费用

{{ investigation_scope }}

{{ cost_summary }}

{{ stop_reason }}

{{ next_stage_instruction }}
