# {{ title }}

{{ decision_paragraph }}

## 这个问题为什么值得做

{{ motivation_paragraph }}

{{ knowledge_gain_paragraph }}

## 与最接近工作的区别

{{ nearest_work_paragraph }}

## 核心判断和另一种解释

{{ hypothesis_paragraph }}

{{ alternative_paragraph }}

## 最小验证怎么做

{{ test_paragraph }}

{{ result_interpretation_paragraph }}

## 需要多少资源

{{ resource_paragraph }}

## 最可能失败在哪里

{{ risks_paragraph }}

{{ unresolved_paragraph }}

## 当前版本与下一步

{{ version_paragraph }}

{{ next_step_paragraph }}

## 来源

{% for source in sources %}
- [{{ source.id }}：{{ source.title }}]({{ source.url }})
{% endfor %}
