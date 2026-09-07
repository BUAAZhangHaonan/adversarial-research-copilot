# 自然 rendering develop：工具参数暂停只读复核

核查时间：2026-09-07 09:41:25.816768 UTC。远端 HEAD：`1667bd8b528e98a2359e767404dedbd977e16e4d`。只读该任务已保存的 request/response/trace/ledger 与当前参数校验函数，没有调用工具执行函数、模型或 MCP，没有重试、科研状态或代码修改，也未干预另一路 Pro 请求。

## 最小根因

模型调用 `read_record` 时传入 **limit=30000**，而当时实际发送给模型的 JSON schema 明确限制 **maximum=24000**。保存 request 的广告 schema 与当前执行参数 schema 完全相同。唯一 JSON Schema 错误是：

```text
instance path: limit
schema path: properties.limit.maximum
validator: maximum
30000 is greater than the maximum of 24000
```

因此这是模型参数违反已公布约束，不是工具广告与执行校验不一致的实现缺陷。此前 `read_web(max_chars=30000)` 合法，但它是另一个工具及另一个参数，不能据此推导 `read_record(limit=30000)` 合法。本次不推测模型为何混用数值。

当前实现没有需要据此放宽或修正的 schema。不能将参数静默夹到 24000 后重放，或修改已保存工具请求。如果以后单独增加离线回归，最小有效用例应以实际广告 schema + limit=30000 验证：模型响应原件保留、暂停 TOOL_ARGUMENTS_INVALID、工具 handler/工具预留均不发生；另以合法边界 24000 为对照。本次未改变已有策略或运行该重放。

## 实际调用与状态

- Run：`arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.develop`。
- Task：上述 run 加 `.fresh_verification`。
- Model call：`call_63d909286a24422a81640af3981f286d`，请求/返回均为 `deepseek-v4-flash`，09:39:20.318327–09:39:25.688461 UTC，finish_reason=`tool_calls`。
- Provider tool call ID：`call_00_aer2oAZDTdZklYeEi3yP7241`；工具名 `read_record`。

原始参数：

```json
{"record_id":"src_c00f46a360304574896b0685b84532c5","offset":0,"limit":30000}
```

该 source_id 确实已登记。失败工具 ID 不存在于该任务的 tool_trace，也不存在于账户 budget_calls 的 metadata.tool_call_id，说明拒绝发生在实际工具执行和工具费用预留之前。不能把它记为一次完成的原文读取。

Run 已为 `PAUSED_PROTOCOL / TOOL_ARGUMENTS_INVALID`。Task 保留最后模型响应的 `RESPONSE_SAVED` 状态，`error=null`，更新时间 09:39:25.755545 UTC；不能把 task 的空 error 误解为 run 没有失败。该 fresh_verification 原账本共 27 行，已计费用 **0.688819–0.688825 CNY**。本次只引用原账本，没有新增请求或改账。

## 广告与执行校验

实际 request 中 `read_record.parameters`：

```json
{"additionalProperties":false,"properties":{"limit":{"maximum":24000,"minimum":1,"type":"integer"},"offset":{"minimum":0,"type":"integer"},"record_id":{"type":"string"},"version":{"minimum":1,"type":["integer","null"]}},"required":["record_id"],"type":"object"}
```

只读调用纯校验函数得到 `MCPFailure: TOOL_ARGUMENTS_SCHEMA`。代码路径：

- `src/arc/runtime.py:153`：定义 limit 的整数范围 1–24000。
- `src/arc/mcp_client.py:58`：`validate_arguments` 检查 JSON 对象、未声明参数和 Draft202012Validator；此例只有 maximum 失败。
- `src/arc/runtime.py:687`：校验实参；`:689` 将错误转换为 `RuntimePaused('PAUSED_PROTOCOL','TOOL_ARGUMENTS_INVALID')`。该检查在工具 reserve/执行之前。

没有读取或输出 reasoning/COT。这里只证明参数与验证规则一致，不评价原研究卡或其他检索结论。

## 原件与哈希

以下路径相对于 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation/artifacts/`。公共任务目录：

`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.develop/tasks/33b4e9b38e1c0023c718decfa9b15fdf31383c149d94aef03107ab26d67f2ee3/`

| 原件 | SHA256 |
|---|---|
| `requests/call_63d909286a24422a81640af3981f286d.json` | `d9756a1b479b86ea1354c94839ffc09e01b9a7d99ecc2e60e1dd35e56097b45d` |
| `states/4adf227d965c4e5d96bc446d1a3fd7e7.json`，账本绑定的响应原件 | `08e7fb8a88ad0fac0fba6c8d9ccaafed8012251d6c544c09785e15821d09dd5a` |
| `states/bb12b72b6c174b7686108b6dbfdf50b7.json`，当前 task 保存状态 | `7cc2ee5e725dc60d99e030ec036cdf5eb8fe4fc7e82396bf852268c129042d93` |
