# L2 新 schema run 导入：协议失败只读复核

核查时间：2026-09-07 09:52–09:54 UTC。远端 HEAD：`1adbc96744893d3a33b16a735ff683d42fc953e4`。本文仅覆盖已暂停的 `explicit_input_schema_v2.run.import`；没有检查或预判仍在运行的 develop import。未调用模型/MCP、重试、修改代码、提示词、账本或研究结果；未展示 reasoning/COT。

## 结论

**首稿是有效 JSON，并非空正文。首次失败是两个相同资源对象触发了未在广告 JSON Schema 中表达的跨字段规则；一次修复后的完整输出则出现真正的 JSON 语法与字段层级错误。**

这两层原因必须分开：不能把首稿描述为违反已广告的 JSON Schema，也不能因为首稿存在接口可见性缺口，就把损坏的修复稿追认为有效。当前 `INVALID_OUTPUT_AFTER_REPAIR` 确实对应第二次输出仍无法解析。没有发现 assembler 丢正文或运行时使用了不同版本的 JSON Schema。

## 原始返回与一次修复

Run：`arc-vnext-validation-20260907.explicit_input_schema_v2.run`。
Task：上述 run 加 `.import`；实际 prompt ID 为 `developer.IMPORT`，结果类型为 `Envelope[DeveloperResult]`。

最终 `PAUSED_PROTOCOL / INVALID_OUTPUT_AFTER_REPAIR`，更新时间 `09:50:30.853120 UTC`，`repair_count=1`。本 task 原账本共 **16 行，0.622656–0.622660 CNY**。

| 模型最终回答 | call_id | 字符数 | finish_reason | 已结算费用 CNY |
|---|---|---:|---|---|
| 首稿 | `call_d6f20fdd650b4de68f64306cc4b678eb` | 21760 | stop | 0.114386–0.114387 |
| 一次结构修复 | `call_b6baaf9a214745e48fbef01531c1d08c` | 18076 | stop | 0.181891 |

两次均为 deepseek-v4-flash。首稿调用 09:48:02.662541–09:49:02.474649 UTC；修复调用 09:49:02.586585–09:50:30.626118 UTC。上述两笔是最终回答阶段，不能将其之和替代含先前检索与模型请求的 task 总费用。

两次保存的 SDK chunk 中 `content` 逐段拼接都精确等于 `response.message.content`。本审计检查保存的 SDK 解析对象，不声称进行了独立网络抓包。

### 首稿：资源对象的额外跨字段约束

首稿 `json.loads` 成功，JSON 根对象与 DeveloperResult 字段齐全。Pydantic 只报告两项相同错误：

```text
result.proposed_revision.resources: positive_gpu_hours_require_gpu
result.resources: positive_gpu_hours_require_gpu
```

这两处资源对象完全相等，其中：

```json
{"gpu_count":0,"training_gpu_hours_range":{"lower":0,"upper":0,"unit":"GPU-hours"},"inference_gpu_hours_range":{"lower":0,"upper":12,"unit":"GPU-hours"},"gpu_memory_gb_assumption":24}
```

原正文的资源解释是“主路径 0 GPU；必要时单张 RTX 3090 补充预测”，即混合了 CPU 主路径和可选 GPU 路径。当前 `ResourceEstimate.units`（`src/arc/schemas.py:193–194`）对单个结构对象要求：`gpu_count=0` 时，任何 GPU-hours 上界不能为正，因此拒绝这两个资源对象。

**可验证的接口差异：**保存 prompt 中的完整广告 schema 与当前 `Envelope[DeveloperResult].model_json_schema()` 完全相同；但对首稿执行 `Draft202012Validator(advertised_schema)` 得到 **0 个错误**。`ResourceEstimate` 广告 schema 没有表达该跨字段条件的 `if/then/allOf` 等内容。实际原 prompt 要求说明 GPU 数量、GPU-hours、工作量与不确定性，并区分最小检验和后续扩展，但没有显式写出 `gpu_count=0` 与正 GPU-hours 不兼容这条硬规则。

这说明首次拒绝存在“实际 typed 校验比公布的机器 schema 更强”的协议可见性缺口。它不是 schema 文件版本错配，也不自动说明该跨字段一致性规则本身错误。本次不修改数据模型或资源估计，不替模型选择 CPU/GPU 路径。

### 修复稿：完整 JSON 语法损坏

修复 prompt 已明确包含第一次的 `positive_gpu_hours_require_gpu` 错误。修复后的完整响应仍被拒绝，精确错误为：

```text
Pydantic: json_invalid
Invalid JSON: trailing characters at line 1 column 33261
Python json.loads: Extra data: line 1 column 15678 (char 15677)
```

两处位置一致：Python 字符位置 15677 对应 UTF-8 字节位置 33260，Pydantic 的报错列为其下一列。该位置在过早闭合的根对象之后，余下 2399 字符从以下片段开始：

```text
,"evidence_requests":[{"request_local_id":"er_closest_boundary_iou_fulltext",...
```

仅读取第一个 JSON 对象用于定位发现，`affected_claims/evidence_review/minimal_test/resources/remaining_issues/next_action` 被放到了 envelope 顶层，而不是 result 内；第一个根对象又缺 envelope 的 evidence_requests、capability_requests、note。仅截去尾部也不能得到合格的 `Envelope[DeveloperResult]`：该前缀仍有 9 个 missing 和 6 个 extra_forbidden。这个分析没有将截取对象保存为候选、验收结果或调用输入。

最终错误不是资源字段仍有同样问题的简单重复，也不是可以安全忽略尾部说明的情况。当前一次修复上限按规则停止。

## 原件与 SHA256

根目录：`/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/`。
公共任务目录：

`runs/arc-vnext-validation-20260907.explicit_input_schema_v2.run/tasks/76ae92933d517bcfef8ef5d97bcb6ad652a5e3a5b06b8d69bbc9f081695f75f9/`

| 原件 | SHA256 |
|---|---|
| `prompt.json` | `9ed106f2f1c98ac2b3e9b06d4ad0cb9e00f5cd763c988b42b63d593d96de38e1` |
| `repair.json` | `cf7961d3bc6827c5adc1f80686aeebbcfcffafbd7f224a7ab7a8475c8a784d25` |
| `requests/call_d6f20fdd650b4de68f64306cc4b678eb.json` | `a0d49a629738b380538f315bfbce7c755faf934b7a845a0e337c9fcfe69a1b8e` |
| `states/3662417807214196ae0c6f79e545e54f.json`，首稿响应 | `4ae385d2d41767bfc722a77b57918dbf7fa82a4fac370012fc21ac64fae9ba8a` |
| `requests/call_b6baaf9a214745e48fbef01531c1d08c.json` | `0213ca276708c70395b8c0cb0e0463ffa07d6135e3638ddbd5d2d812ddb0744c` |
| `states/8da780860d1d46ddbfc988d083f848c9.json`，修复响应 | `61c293da40f80362eb6b1836efebab4a43cab7c4f324301a29d7125074d9b1dc` |
| `states/04407322efe9415f82936d54a77bc749.json`，最终暂停状态 | `0c2101b11fb45c9b059c7117e784bdb7f3816fc3ae0335a8e770624759b8efb8` |

正文 UTF-8 SHA256：首稿 `f8af0fe5712eaf8002490da03c09ad6f4d193655cf57f0ab89570af8bf45a2d5`；修复稿 `d841e78be5b0965c377d25d0952247a3dbba86857c3b282a0c9b174fff46b732`。

校验只使用已保存 JSON、当前 Pydantic/JSON Schema 纯校验函数和 SQLite 只读连接。本文不评价模型科学结论，也不将尚未结束的 develop 路线纳入结果。
