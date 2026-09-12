# ARC 模型与 MCP 接口核查

> 历史记录：旧 worktree 已移除；当时的 `work/mcp_tools_audit.json` 现位于主仓库 `work/legacy-20260907/mcp_tools_audit.json`。见 [档案归并记录](ARCHIVE_CONSOLIDATION_20260912.md)。


核查：2026-09-07；只改 ARC 隔离目录。没有修改或重启服务，没有调用收费研究方法。

## 接口快照

[DeepSeek 官方人民币价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) 当天仍为 Flash-0731 / Pro-0813，1M context、最大 384K output。`configs/pricing.json` 保存人民币价及公告版本；PriceBook 计算文件 SHA256，逐请求记录快照 ID/hash。公告版本不能证明某次请求用了对应权重。

[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/) 明确支持 `reasoning_effort=max`、`thinking.type=enabled`；含 tools 的历史须完整回传 reasoning_content。[Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) 说明最后内容块携带 usage/finish_reason，不能只处理独立 usage 块。

SDK 实测：MCP 2.1.1、OpenAI 2.54.0。MCP [当前稳定版是 v2](https://github.com/modelcontextprotocol/python-sdk)，[Client](https://py.sdk.modelcontextprotocol.io/client/) 接管握手、协议协商和生命周期。SSE/stdio 使用官方 transports，没有自写 JSON-RPC 或 readline。

## 真实 tools/list

在 `/home/g203/zhanghaonan/arc-vnext-20260907/.venv` 使用 MCP 2.1.1 连接既有配置；成功清理 SDK 会话与自行启动的 stdio 子进程。原始清单保存在该目录 `work/mcp_tools_audit.json`。

| 服务 | 协议 | 实际工具 |
|---|---|---|
| ScholarTrace | 2025-11-25 | query, read |
| ScholarAnalysis | 2025-11-25 | get_paper_text, analyze_paper |
| webresearch-mcp | 2026-07-28 | web_search, fetch_page, research, list_resources, get_resource |

参数来自实际 inputSchema。ARC 只映射事先审计的 read/search 操作，原始第三方 description 仅入审计快照，模型工具说明来自 ARC Markdown。源材料不能改变工具注册表或取得 shell。URL 参数拒绝非 HTTP(S)、用户凭据和本地/私网字面地址；既有服务自身也须保持 URL 访问限制，ARC 不修改其实现。

## 外部费用边界

以下零费用指外部按调用付费 API 费用，不指本地计算没有资源成本。

| 操作 | 结论与依据 |
|---|---|
| webresearch.web_search | 0 元模型/API费。`src/webresearch_mcp/server.py:56` 调用 `pipeline.py:128`；仅已有搜索引擎召回和确定性排序，未经过收费 agent。配置模块也把 DeepSeek 排名代理声明为唯一外部 AI API。 |
| webresearch.fetch_page | 0 元模型/API费。`server.py:62` → `pipeline.py:91` HTTP 获取、解析、保存，没有模型调用。 |
| ScholarAnalysis.get_paper_text | 0 元外部模型/API费。`scholar_analysis/mcp_server.py:147` → `pipeline/orchestrator.py:100-156` 本地 arxiv_mirror 下载及 MinerU 解析。只读核对现有配置分别为回环 8900 与 8000；这条路径未执行 PostProcessor。 |
| ScholarTrace.query | COST_UNOBSERVABLE。`scholartrace/api/mcp_server.py:218` 调用完整 run_query_pipeline；检索重试、theme parser、多轮模型排序等内部成本未完整暴露为逐请求账单/可核验最大费用。没有因为它是本地 MCP 就认定免费。 |
| ScholarAnalysis.analyze_paper | 存在收费后处理，token_usage 是局部返回；此次不映射此方法，使用真实原文工具。 |
| webresearch.research | 可调用 LLM 排名代理，此次不映射；不改变其 use_llm 或服务模型配置。 |

因此，真实 E2E 可以使用现有 web_search、fetch_page 与 get_paper_text；不能声称已验收 ScholarTrace 的收费研究链路。解除 query 阻塞需要服务提供可靠的单次费用上限或完整内部模型/重试/最大调用次数/价格约束，并可记录真实 usage 或保守结算。不要求 ARC 开发者修改这些服务。

## 直调准入与结算

为全部语义调用保留完整 384K 输出额度；请求不随余额降强度或缩短上限。[官方 Pi 配置](https://api-docs.deepseek.com/quick_start/agent_integrations/pi_mono/) 给出精确的 `contextWindow=1000000`、`maxTokens=384000`，请求使用 384000，不把 K 猜成二进制乘数。[官方 Oh My Pi 配置](https://api-docs.deepseek.com/quick_start/agent_integrations/oh_my_pi/) 明确 thinking mode 不发送 `tool_choice`，因此 ARC 使用省略字段后的默认自动工具选择。准入不猜字符/token比例：在 provider 强制 `input+output<=context`、`output<=max_output` 且输出价高于输入价的边界内，最大费用为 `context*miss_price + max_output*(output_price-miss_price)`。使用高峰价可覆盖未知响应长度及未公开的跨时段计价规则。

价格页于 `2026-09-07T02:20:07.525892+00:00` 读取 HTTP 200，HTML SHA256 为 `899affbdbc33d0be620d8dea59e86f5036c11b5410b14d060b8d2874c74f38e5`。接口页于 `2026-09-07T02:20:06.158005+00:00` 读取 HTTP 200，HTML SHA256 为 `67b6a6c8ab70f51ad56f6018077ac58768d95f73b53639b4d00b3f6d57a4fad9`。HTML 变动只能提示重新核对，不能直接等同价格变动。

完成后按 usage 与开始/结束间可能时段计算费用范围，reasoning 已包含在 completion 中。每次请求保存不可变价格文件，恢复时核对原文件 SHA256 并按原价结算；新的请求才使用新的价格快照。缺缓存明细保留命中/未命中区间，缺 usage 用保守上界，不写成实测账单。断流和结果未知保留预留，禁止 SDK 自动重试。

离线验证使用真实 OpenAI SDK 加本地 HTTP transport fixture，检查完整输出上限、max thinking、原生工具关联、包含 reasoning 的后续消息、原始响应保存后的恢复、结构修复次数、预算拒绝与未知结果不重发。MCP 验证包含官方 SDK 内存服务、静默/半行/EOF stdio 和静默/EOF SSE；SDK 生命周期使用 AnyIO 的取消作用域，保证超时后清理它启动的子进程。这些测试不替代真实付费模型 E2E。
