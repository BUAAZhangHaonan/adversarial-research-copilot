# MCP 能力需求与已验证边界

日期：2026-09-07。只读审阅现有服务；没有修改、重启或升级服务。

## 已接通

ARC 通过官方 MCP SDK 对现有 SSE/stdio 服务执行 initialize 和 tools/list，使用服务实际返回的输入 schema。

- webresearch：`web_search`、`fetch_page`，映射为 ARC `search_web`、`read_web`。已只读核对实现，这两条路径不调用付费模型；账本中的 0 元仅指外部 API 费用，不能解释为没有服务器计算成本。
- ScholarAnalysis：`get_paper_text`，映射 `read_paper`。通过现有 arxiv mirror/MinerU 读取原文，不调用付费分析后处理。
- 本地：`lookup_archive`、`read_record`、`request_capability`。只读档案及来源，能力需求写入 ARC 自己的状态。模型没有 shell、文件任意写入或调预算工具。

完整实际清单和协议版本见 `SERVICE_AUDIT.md`，每个真实 run 保留独立 `mcp_inventory.json`。

## 当前阻塞

ScholarTrace `query` 内部使用模型并有重试；本次只读接口不能提供可验证的逐调用费用上界。ARC 将这项能力标记 `COST_UNOBSERVABLE`，不将其作为可执行工具，不假定免费。ScholarAnalysis `analyze_paper` 和 webresearch `research` 也不作为免费替代路径。

解除此阻塞需要服务提供以下只读契约之一：

1. 调用前返回本次操作所有模型/重试/下游费用的人民币硬上界，调用后返回 request_id、usage/人民币费用和可信度；
2. 可验证的固定价或明确免费策略，包含下游服务收费边界。

仅有账户余额、模型名或预估 token 均不足以证明逐调用上界。此需求只写入 ARC 文档，没有自行修改服务。

## 证据边界

成功检索不能证明新颖性，搜索空结果也不能证明不存在。搜索摘要保留 metadata 身份；MCP 生成分析保留 secondary_analysis 身份。只有保存的实际原文及可验证摘录/位置才能形成 verified evidence。代码校验存在性和摘录一致性，主张支持关系仍由读到原文的模型判断并留解释，不等同专家验证。

部分外站实际返回 HTTP 403，访问失败会保留在 trace；应根据未核对的关键主张缩小结论，不能自动重复收费路径、换主题或将其记为科研否决。
