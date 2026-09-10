# {{ report_title }}

{{ conclusion }}

{% for item in discuss %}
## {{ item.title }}

{% if item.current %}{{ item.insight }}

{% endif %}{{ item.reason }}

主要风险：{{ item.risk }}

{% if item.relation %}候选关系：{{ item.relation }}

{% endif %}[阅读预研卡]({{ item.path }})
{% endfor %}

{% if leads %}
## 还值得留意的线索
{% for item in leads %}
**{{ item.title }}**

{% if item.current %}{{ item.insight }}

决定性未知：{{ item.risk }}

{% endif %}待查：{{ item.reason }}

{% if item.relation %}候选关系：{{ item.relation }}

{% endif %}[阅读线索]({{ item.path }})
{% endfor %}
{% endif %}

{% if pending %}
## 待预研
{% for item in pending %}
**{{ item.title }}**：{{ item.insight }}

{{ item.reason }}。尚未完成预研，不能当作推荐。

{% if item.relation %}候选关系：{{ item.relation }}

{% endif %}[查看已保存灵感]({{ item.path }})
{% endfor %}
{% endif %}

{% if skipped %}
## 本次没有继续的方向
{% for item in skipped %}
- {{ item.title }}：{{ item.reason }}{% if item.current | default({}) %}；当前认识：{{ item.insight }}{% endif %}{% if item.relation | default('') %}；候选关系：{{ item.relation }}{% endif %}{% if item.path %}（[查看记录]({{ item.path }})）{% endif %}
{% endfor %}
{% endif %}

## 共享调研概览

以下概览形成于调研阶段，后续候选预研可能修正其中的背景与缺口判断；以各卡当前预研判断和实质调整为准。

{{ landscape_summary }}

## 调查与费用

{{ investigation_scope }}

{{ cost_summary }}

{{ stop_reason }}

{{ next_stage_instruction }}
