# 能力与改进需求

需求：{{ record.request_id }}

运行：{{ record.run_id }}

来源任务：{{ record.task_id or '人工登记' }}

状态：{{ record.status }}

## 原始需求

{{ request_json }}

## CodeX 评估交付模板

请核对上述实际限制与相关实现，评估提议是否合理，比较当前替代方案，推荐最小可行选项。
将评估写为 JSON，字段为 assessment（recommended / needs_information / not_recommended）、
rationale、recommended_option（无建议时为 null）、implementation_scope（列表）、validation_plan（列表）。
本步骤仅评估，不执行变更。用 arc requirements review 记录评估。

{% if record.review is not none %}
## 已记录的 CodeX 评估

{{ review_json }}

{% if record.review.assessment == 'recommended' %}
## 用户执行支线交付模板

用户决定采用后，可将以下文本交给 CodeX；本文件没有创建或启动任何任务。

基于需求 {{ record.request_id }}，请实施已评估选项：{{ record.review.recommended_option }}

实施范围：

{% for item in record.review.implementation_scope %}
- {{ item }}
{% endfor %}

完成验证：

{% for item in record.review.validation_plan %}
- {{ item }}
{% endfor %}

交付修改文件、验证结果及未完成项。保留原研究记录；不得把能力改善当成科研证据。
{% else %}
当前评估没有推荐实施选项，不生成执行支线。
{% endif %}
{% else %}
尚未评估，不生成执行支线。
{% endif %}

登记、评估和导出均不授权安装工具、修改服务、放宽工具限制或增加预算。
实际执行前，由用户明确选择执行范围；涉及新增费用或服务权限时单独取得授权。
