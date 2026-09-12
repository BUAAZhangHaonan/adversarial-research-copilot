# 最后一次独立run的工具协议核查

2026-09-07 10:36:17.291491 UTC起，只读g203隔离worktree的SQLite、保存请求及固定状态文件。核查没有发起模型/MCP调用，没有重试、修原稿或干预driver；没有查看或展示reasoning_content。

结论：这是模型提交的工具参数超过已公开上限。实际请求广告schema与运行时冻结工具schema完全相同，拒绝发生在工具调用登记、预留及handler执行之前。新资源schema确已进入真实请求，但本次没有可接受的最终科研输出，不能据此宣称输出或run入口验收成功。

## 精确失败

Run：`arc-vnext-validation-20260907.explicit_input_schema_v3.run`，主线程已测代码标识为 `a14da30`。保存状态为PAUSED_PROTOCOL / TOOL_ARGUMENTS_INVALID；card_id/card_version均null，唯一import task停在RESPONSE_SAVED，repair_count=0。

原模型请求 `call_a81e260f90974b66ba33ac6880faae68` 于10:35:52.618420 UTC完整返回，finish_reason=tool_calls。模型要求：

```json
{"name":"read_record","tool_call_id":"call_00_9vRwBvShybP6apuG3JFM9089","arguments":{"limit":52265,"offset":40000,"record_id":"src_10281ffcb6e44dedabeb1e2f1e156b6b"}}
```

实际发送的read_record.parameters规定limit为integer、minimum=1、maximum=24000。独立使用该请求内的schema重验，唯一参数错误为路径 `limit`、validator=`maximum`：`52265 is greater than the maximum of 24000`。ARC的validate_arguments也重现TOOL_ARGUMENTS_SCHEMA；Runtime将它映射为TOOL_ARGUMENTS_INVALID。这不是隐藏的额外参数规则或科学否决。

已核对最终模型请求的tools与固定状态tools逐字段完全相等；冻结prompt中的system/user消息都存在于该实际请求。请求使用deepseek-v4-flash、reasoning_effort=max、max_tokens=384000、response_format=json_object、stream=true。

## 未执行及费用边界

- 该provider tool_call_id在固定tool_trace中出现0次，在整个budget_calls表的metadata.tool_call_id中出现0次；pending_tool=null，没有生成对应ARC tool_*执行ID。
- `src/arc/runtime.py:680` 的_execute_tool先解析并validate_arguments；失败在第689行抛出。工具ID生成、ledger.reserve和handler均在其后。因此该非法工具没有执行、没有预留、没有新增工具费用。
- 不把上述结论写成整个run免费：返回非法参数的模型请求已经SETTLED，实际估计费用0.005250元。run共39调用，全部SETTLED，总计0.294770–0.294781元，reserved=0。此前成功或失败的工具与模型费用均保留。

## 新prompt与资源schema的实际可见性

run.prompt_version为 `bundle-sha256:dd0ddf4c247756f233e52742119796a4bd604f1a39138532d572e007b23b5dc2`；run.code_version为 `arc-0.2.0:5015eed58a4baa3696594e0d83bd155cd44ade23b242de6e4782d454297ea50c`。prompt_id为developer.IMPORT，完整prompt_hash为 `eb50bde36a4c74b818af465cbffbe89c9c4e902793fdd928a21e1ea08fddef56`。

冻结Required JSON schema的ResourceEstimate已通过allOf公开：wall_hours_range单位hours；training/inference单位GPU-hours；gpu_count>0需非空gpu_type及正数显存；gpu_count=0时GPU-hours上界不可大于0。WorkloadAssumptions七个字段均在required中，可空字段仍需按schema给出。这些约束确实在本次实际请求的用户消息中，并非只存在于后来的源码；这仅证明可见性，不证明模型已正确产出资源对象。

| 审计对象 | SHA256 |
|---|---|
| 实际read_record参数schema | 43233ce8c5331cd1c9f21a9c2aff028db14c5cb200a29587054336cd3131dbcb |
| 实际完整tools数组 | dd66c7f12a21c0b63a351f162356c1a17816121c142433cf2e27e07d84800251 |
| 冻结Required JSON输出schema | b343189fa2a1f6c290dced93cf84e043c613fa6298e735038bf10e1167d9aed8 |
| common/resource_policy.md原文 | 7b41ff703e9e21e774d8c6b4ebead05e07c3d49d7c4c3f5da8d41f7ffe1d739d |
| 实际read_record Markdown工具描述 | 078c7bf83237b06fb086fbd290baea1437b1cecb679beaabae1b9f6fa8f3c36e |

前三项结构对象hash采用sort_keys=true、ensure_ascii=false、separators=(',',':')的JSON字节；后两项为原文UTF-8字节hash，不混同完整prompt文件hash。

## 固定原件

共同根目录为g203 `/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/`，任务目录为：

`runs/arc-vnext-validation-20260907.explicit_input_schema_v3.run/tasks/a80812dd6db9530388f520ad7d271d042e0c4d648e75e54b24ad7af526f3d0e0/`

| 任务目录内路径 | 原件字节SHA256 |
|---|---|
| prompt.json | f2904ceafb3bb2ffbcbfc09bddd98a22c11ceab42856f10f390d7075d4d49a1a |
| requests/call_a81e260f90974b66ba33ac6880faae68.json | 5513c63ac1e25a901e5c3a06621ed20d1e8f98ac4aaeeef9d79954e895ec5778 |
| states/566df0a1fbb34dbfb39c9da65877f45d.json（模型已结算响应） | b8722aad0b6649ce28c7fc03ca08289a86e8946505789e684fcf5ad9590309be |
| states/12fe459e74134201ac83075aafb2f0d5.json（最终task指向） | 77c3fb29bf2ef1d45a3986cf76bfd3e777406edf62fb27a2afcd5a9956489fb7 |

最终费用与全局交付状态由VALIDATION_SNAPSHOT、COST_REPORT及最终续跑记录汇总。本审计只确认该次参数拒绝、实际广告schema一致性和工具未执行边界，不修旧输出，也不重发任何请求。
