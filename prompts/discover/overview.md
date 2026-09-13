# {{ report_title }}

{{ conclusion }}

{% for item in discuss %}
## {{ item.title }}

{% if item.current %}{{ item.insight }}

{% endif %}{{ item.reason }}

{% if item.risk %}需要先弄清：{{ item.risk }}

{% endif %}{% if item.relation %}与其他想法的关系：{{ item.relation }}

{% endif %}[阅读预研记录]({{ item.path }})
{% endfor %}

{% if leads %}
## 保留的线索
{% for item in leads %}
### {{ item.title }}

{% if item.current %}{{ item.insight }}

{% endif %}{{ item.reason }}

{% if item.current and item.risk %}主要未知：{{ item.risk }}

{% endif %}{% if item.relation %}与其他想法的关系：{{ item.relation }}

{% endif %}[查看线索]({{ item.path }})
{% endfor %}
{% endif %}

{% if pending %}
## 尚未完成预研
{% for item in pending %}
### {{ item.title }}

{{ item.insight }}

{{ item.reason }}

{% if item.relation %}与其他想法的关系：{{ item.relation }}

{% endif %}[查看已保存灵感]({{ item.path }})
{% endfor %}
{% endif %}

{% if skipped %}
## 本次放下的方向
{% for item in skipped %}
### {{ item.title }}

{{ item.reason }}

{% if item.current | default({}) %}{{ item.insight }}

{% endif %}{% if item.path %}[查看记录]({{ item.path }}){% endif %}
{% endfor %}
{% endif %}

## 领域认识

{% if not landscape_updated %}以下是前期调查概览，候选预研中的更新见相应记录。

{% endif %}{{ landscape_summary }}

## 调查与运行记录

{{ investigation_scope }}

{{ cost_summary }}

{{ stop_reason }}

{{ next_stage_instruction }}
