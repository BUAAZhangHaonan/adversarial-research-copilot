# {{ title }}

{{ status_text }}。尚未完成候选预研，不是已推荐结果。

**核心想法**

{{ insight }}

**研究问题**

{{ question }}

**为什么值得看**

{{ why_it_matters }}

**与已知认识的差异（构思者的初步判断）**

{{ difference }}

**当前处理与未知**

{{ reason }}

{{ unknown }}

{{ questions }}

## 启发来源

{% for source in sources %}
- {% if source.url %}[{{ source.title }}]({{ source.url }}){% else %}{{ source.title }}{% endif %}：{{ source.relevance }}（{{ source.access_text }}）。
{% endfor %}

{{ provenance_line }}
