# 开发验证的预算追加授权

唯一父账户为 `arc-vnext-validation-20260907`，总额始终不超过100元。生产默认仍为每阶段20元；阶段追加只改变该账户可用限额，不代表实际花费，不增加父级总额，也不重置历史账目。

## 早期三个旧账户

用户回复“允许各追加5元，总额仍不超过100元”后，于2026-09-07 08:39:14.754059 UTC 应用：

| 账户后缀 | 原限额 | 追加 | 新限额 |
|---|---:|---:|---:|
| ARC_RENDERING_VALIDATION.discover | 20元 | 5元 | 25元 |
| explicit_input.develop | 20元 | 5元 | 25元 |
| ARC_VNEXT_VALIDATION_V3.discover.comparison.direct-Pro | 20元 | 5元 | 25元 |

原始批准范围和应用结果保存在历史验证目录的 `work/approved-budget-extension.json` 及 budget_authorizations 中。

## 本轮两个新阶段的条件授权

用户另行明确选择“允许本轮两个新阶段需要时各追加5元，父级仍100元”。该授权仅覆盖：

- `natural_runtime_versions_v2.develop`
- `natural_runtime_versions_v2.run`

只有各阶段实际进入 PAUSED_BUDGET 才应用一次5元，20→25元；不为其他阶段或第二次追加提供授权。

本轮 develop 在已结算4.740012–4.740035元时暂停，因为20元账户剩余15.259965元不足以预留下一次Pro请求的15.912元。当前请求已自然结束、预留及未知调用均为零。于2026-09-07 14:22:25.621746 UTC 应用 develop 的5元追加，然后继续原任务检查点；未重跑已完成角色。

run 的应用情况以本轮最终费用报告和私有 `work/runtime-version-budget-authorizations.json` 为准；授权本身不表示已经使用。最终实际限额见 [COST_REPORT.md](COST_REPORT.md)。

账本 budget_accounts 保存实际限额，budget_authorizations 保存理由和追加金额。两轮授权、已发生费用和失败记录全部保留。当前费用导出使用只读事务，不执行额外文件哈希校验。
