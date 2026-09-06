# COST_REPORT

## ARC-owned LLM calls (billed to the configured DeepSeek key)

| model | calls | prompt tok | completion tok | total tok | wall time (s) | reports w/o usage |
|---|---:|---:|---:|---:|---:|---:|
| deepseek-v4-flash | 2 | 1719 | 17081 | 18800 | 137.5 | 0 |
| deepseek-v4-pro | 11 | 37598 | 56975 | 94573 | 956.1 | 0 |

## MCP service calls (billed to each service's own key)

- scholartrace: 24 tool calls
- scholaranalysis: 13 tool calls
- webresearch: 17 tool calls

Note: MCP services run their own LLM pipelines internally and do not
report token usage to ARC; their cost is only bounded by these call
counts, not measured. Reports without usage are gateway responses that
omitted the usage field (recorded as zero, flagged in the last column).
