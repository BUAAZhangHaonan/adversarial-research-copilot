# MCP 能力需求与已验证边界

服务审计日期：2026-09-07；ARC 授权接线更新：2026-09-11。没有修改、重启或升级 MCP 服务。

## 已接通

ARC 通过官方 MCP SDK 对现有 SSE/stdio 服务执行 initialize 和 tools/list，使用服务实际返回的输入 schema。

- webresearch：`web_search`、`fetch_page`，映射为 ARC `search_web`、`read_web`。已只读核对实现，这两条路径不调用付费模型；账本中的 0 元仅指外部 API 费用，不能解释为没有服务器计算成本。
- ScholarAnalysis：`get_paper_text`，映射 `read_paper`。通过现有 arxiv mirror/MinerU 读取原文，不调用付费分析后处理。
- 本地：`lookup_archive`、`read_record`、`request_capability`。只读档案及来源，能力需求写入 ARC 自己的状态。模型没有 shell、文件任意写入或调预算工具。

完整实际清单和协议版本见 `SERVICE_AUDIT.md`，每个真实 run 保留独立 `mcp_inventory.json`。

## 已授权的未计量调用

ScholarTrace `query` 内部使用模型并有重试；现有接口不能提供可验证的逐调用费用上界。用户已明确允许在费用未计量时使用它。ARC 的 `search_literature` 因而配置 `allow_unmetered=true`，同时保留 `cost_upper_cny=null` 和 `COST_UNOBSERVABLE`；这不是免费声明。

授权仅适用于 ScholarTrace `query`，其他费用未知工具继续拒绝执行。ScholarAnalysis `analyze_paper` 和 webresearch `research` 未因此开放。实际入参、原始响应和来源继续存入 ARC trace；没有更改三个 MCP 服务的代码。ScholarTrace 只给内部 paper_id 而无 URL/DOI/arXiv 的条目保留为 `unregistered_candidates`，带标题、摘要、作者、年份及供应商 rationale。它们标为 `identity_unresolved`、不可正式引用；rationale 是二手分析，不能冒充论文原文。Agent 可按标题继续定位公开来源。

账本 `cost_status=unmetered` 的费用与预留对外均为 null，不参与模型预算的已知金额加总。`SETTLED` 仅表示动作记录已经结束，不能解释为金额已知。汇总提供 `unmetered_calls`、`total_cost_complete=false`、`cost_scope=metered_costs_only`，报告明确说明已知金额不是全部费用或总费用上界。数据库既有非空整数列的占位值不作为对外价格。

此工具超时或中断后无法确认结果时，记录 `outcome_status=unmetered_outcome_unknown` 并向 Agent 提供工具错误；不重复原请求，不借此触发模型费用 UNKNOWN 暂停。已有模型请求结果未知、已知工具的费用准入逻辑保持原样。

## 尚缺的计量契约

要将此工具纳入可计量预算，服务需要提供以下只读契约之一：

1. 调用前返回本次操作所有模型/重试/下游费用的人民币硬上界，调用后返回 request_id、usage/人民币费用和可信度；
2. 可验证的固定价或明确免费策略，包含下游服务收费边界。

仅有账户余额、模型名或预估 token 均不足以证明逐调用上界。此需求只写入 ARC 文档，没有自行修改服务。

## 证据边界

成功检索不能证明新颖性，搜索空结果也不能证明不存在。搜索摘要保留 metadata 身份；MCP 生成分析保留 secondary_analysis 身份。只有保存的实际原文及可验证摘录/位置才能形成 verified evidence。代码校验存在性和摘录一致性，主张支持关系仍由读到原文的模型判断并留解释，不等同专家验证。

部分外站实际返回 HTTP 403，访问失败会保留在 trace；应根据未核对的关键主张缩小结论，不能自动重复收费路径、换主题或将其记为科研否决。
