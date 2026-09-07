# 工具协议纠正与改进需求

2026-09-07，用户授权补齐任务纠正和改进提议路径。它们已在 master 实现；当前工具上限、模型配置与账本授权不变。

## 一次有界纠正

原生工具的参数不符合公开 schema 时，运行时保存原始调用、报错字段、校验器和实际 schema，返回 `rejected_before_execution`，不执行非法调用，也不将它计为取证成功。该反馈是协议记录，没有工具付费预留。

模型可以纠正这一批被拒绝的调用，也可以返回 blocked envelope 与具体改进需求。纠正必须保持原工具、调用顺序、目标和所有合法字段；只有报错的完整字段路径可以变化，缺失的必填字段可以补回，无关可选字段不能新增。嵌套对象中的合法目标同样受到保护。无法解析成对象的参数没有可靠的原目标，只能走 blocked 需求路径；复杂联合 schema 未明确定位可变字段时也不授予整对象修改权。

工具参数纠正和最终 JSON 结构修复共享每任务一次额度，`repair_kind` 区分两者。工具纠正成功后，正常研究调用继续；再次非法、改目标、跳过纠正并宣称完成，均暂停。最终 JSON 修复仍禁用工具。来源、引用和科研语义校验没有放宽。

`tool_correction` 保存 preparing、awaiting、executing、completed/declined 阶段；`tool_rejections` 保留拒绝记录。已成功的同批调用按模型响应与工具调用 ID 识别，预算暂停或中断不会重放。纠正提示词来自任务已冻结的 Markdown。旧任务没有该模板或 schema 已变化时仍须明确新建运行版本；不修改旧失败输出或重新授予修复次数。

## 每任务可提出改进

有工具的角色可以调用 `request_capability` 后继续正常研究；所有任务均可在最终 envelope 的 `capability_requests` 登记提议，不要求科研结果先失败。需求进入 `pending_codex_review`，携带来源任务、当前限制、具体建议、理由、替代方案和预期影响。

CodeX 检查实现与约束后，通过 `requirements review` 记录推荐、需补信息或不推荐及理由。推荐时必须有具体选项、实施范围和验收计划；随后 `requirements export` 导出用户执行支线说明。登记和评估都不会安装服务、修改工具上限、增加费用授权或自动创建/启动任务。需求原文与评估均保留，重复登记或恢复不会重复写入。

用法见 [CAPABILITY_REQUESTS.md](CAPABILITY_REQUESTS.md)。[64000 字符实例](READ_LIMIT_SIDE_TASK.md)已完成代码层面的可行性评估，尚未执行容量变更或声称性能收益。64000 字符不等于 64K token。

## 已验证范围

- master `1df1ec4`：最终完整离线测试 370 项通过，79.86 秒；日志为 g203 主仓库 `work/tests-protocol-correction-final.log`。
- 21 项协议测试包含不可解析目标、共享额度和同时出现未知/越界/缺失参数的一次完整反馈。
- `21b0cd2` 的 sdist/wheel 构建及仓库外独立安装检查通过，已验证新 schema、纠正模板及需求交付模板随包加载；后续 `1df1ec4` 只补充同批错误收集，370 项测试已覆盖。
- 实际 SDK MockTransport 覆盖纠正成功、二次失败、目标保护、嵌套错误、额外参数、预算恢复、两处进程中断、兄弟调用不重放、blocked 需求交付。
- 需求测试覆盖 CLI 登记→评估→导出、结果完整或 blocked 均登记、恢复幂等、评估不改变预算和运行状态。

真实自然卡的新版本验证使用旧100元父账本，develop/run 各20元，先 develop 完成才选择其版本进入 run。不会因协议改动把旧失败改为通过；实时及最终结果以 [MASTER_STATUS.md](MASTER_STATUS.md) 为准。

本轮真实复验最终因claim版本依赖错误暂停，未触发工具越界；完整结果及已登记的优先改进见[复验报告](PROTOCOL_CORRECTION_LIVE_RESULT.md)。
