> 历史结算快照：本报告保留上一轮账目。本轮协议改进后新增费用及当前余额见 [真实复验结果](PROTOCOL_CORRECTION_LIVE_RESULT.md)。

# 费用报告

账本快照时间：2026-09-07T10:36:14.234815+00:00。币种为人民币。

唯一开发父账户：`arc-vnext-validation-20260907`；账本实际限额 **100.000000 元**。
已结算估计区间 **45.154048–45.303543 元**；未结算预留 **0.000000 元**；未知调用 **0**；可准入剩余 **54.696457 元**。

限额是允许的累计支出上限，不是已经花费或必须花费的金额。父级支出汇总全部子账户一次；子账户限额不能相加当成父级授权。

以上是实际 usage 按冻结官方价复算或已审计工具上界，不是供应商逐请求人民币账单。区间涵盖缓存明细、跨峰谷规则与整数舍入的不确定性；reasoning 已计入输出，不重复收费。

| 账户（省略父账户前缀） | 实际限额 | 本账户调用数 | 已结算下界 | 已结算上界 | 预留 | 未知 |
|---|---:|---:|---:|---:|---:|---:|
| 父账户自身调用 | 100.000000 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
| protocol.deepseek-v4-flash | 20.000000 | 1 | 0.083568 | 0.083568 | 0.000000 | 0 |
| protocol.deepseek-v4-pro | 20.000000 | 1 | 0.108774 | 0.108774 | 0.000000 | 0 |
| ARC_VNEXT_VALIDATION.discover | 20.000000 | 43 | 0.554694 | 0.554702 | 0.000000 | 0 |
| ARC_VNEXT_VALIDATION_V2.discover | 20.000000 | 96 | 1.733201 | 1.733227 | 0.000000 | 0 |
| ARC_VNEXT_VALIDATION_V3.discover | 20.000000 | 190 | 4.529248 | 4.539975 | 0.000000 | 0 |
| protocol_json_tools.deepseek-v4-flash | 20.000000 | 3 | 0.019979 | 0.019981 | 0.000000 | 0 |
| protocol_json_tools.deepseek-v4-pro | 20.000000 | 3 | 0.077400 | 0.077402 | 0.000000 | 0 |
| explicit_input.develop | 25.000000 | 100 | 4.106986 | 4.107017 | 0.000000 | 0 |
| explicit_input.run | 20.000000 | 654 | 6.464293 | 6.464552 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.discover | 25.000000 | 199 | 8.897677 | 8.897731 | 0.000000 | 0 |
| ARC_VNEXT_VALIDATION_V3.discover.comparison.ARC | 20.000000 | 2 | 1.323994 | 1.323996 | 0.000000 | 0 |
| ARC_VNEXT_VALIDATION_V3.discover.comparison.direct-Pro | 25.000000 | 3 | 7.101934 | 7.101937 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.discover.comparison.ARC | 20.000000 | 5 | 1.808136 | 1.808138 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.discover.comparison.direct-Pro | 20.000000 | 1 | 1.264327 | 1.264328 | 0.000000 | 0 |
| materials.conflict_holdout | 20.000000 | 50 | 1.328487 | 1.328501 | 0.000000 | 0 |
| materials.conflict_holdout.comparison.ARC | 20.000000 | 3 | 0.451487 | 0.451489 | 0.000000 | 0 |
| materials.conflict_holdout.comparison.direct-Pro | 20.000000 | 3 | 1.989082 | 1.989085 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.develop | 20.000000 | 27 | 0.688819 | 0.688825 | 0.000000 | 0 |
| explicit_input_schema_v2.run | 20.000000 | 16 | 0.622656 | 0.622660 | 0.000000 | 0 |
| explicit_input_schema_v2.develop | 20.000000 | 72 | 1.704536 | 1.842874 | 0.000000 | 0 |
| explicit_input_schema_v3.run | 20.000000 | 39 | 0.294770 | 0.294781 | 0.000000 | 0 |

表内支出只计该账户直接登记的调用，避免父子重复求和；未发生调用的账户仍显示实际限额。调用数包含零费用本地读取、真实MCP操作和模型请求。失败、结构修复、恢复、新版本验证、对照与评价均保留原记录，不重置账户。

模型请求数量：`{"deepseek-v4-flash": 566, "deepseek-v4-pro": 43}`。逐调用检查均仅Flash/Pro且effort=max。

## 追加授权与实际限额

生产默认阶段限额仍为20元；上表使用budget_accounts当前限额，不将所有阶段写成默认值。授权来源及范围见 [BUDGET_EXTENSION_AUTHORIZATION.md](BUDGET_EXTENSION_AUTHORIZATION.md)。

用户回复：允许各追加 5 元，总额仍不超过 100 元。执行记录：`work/approved-budget-extension.json`，执行时间：2026-09-07T08:39:14.754059+00:00。

| 账户 | 追加金额 | 账本授权时间（UTC） | 授权理由 |
|---|---:|---|---|
| ARC_RENDERING_VALIDATION.discover | 5.000000 | 2026-09-07T08:39:14.732387+00:00 | user_reply_20260907_call_ka7TskVvAqjblfhfKC5vZqvl: 允许各追加 5 元，总额仍不超过 100 元; only three accounts in work/pending-budget-approval.json |
| explicit_input.develop | 5.000000 | 2026-09-07T08:39:14.739586+00:00 | user_reply_20260907_call_ka7TskVvAqjblfhfKC5vZqvl: 允许各追加 5 元，总额仍不超过 100 元; only three accounts in work/pending-budget-approval.json |
| ARC_VNEXT_VALIDATION_V3.discover.comparison.direct-Pro | 5.000000 | 2026-09-07T08:39:14.746246+00:00 | user_reply_20260907_call_ka7TskVvAqjblfhfKC5vZqvl: 允许各追加 5 元，总额仍不超过 100 元; only three accounts in work/pending-budget-approval.json |

初始及追加授权的全部budget_authorizations原记录保存在JSON快照；追加限额不计入已结算支出，不调整默认配置，不自动授权其他账户追加。每次请求仍须同时满足本账户与父账户准入。

## 准入与实际花费的区别

每个模型请求在启动前，为1M上下文边界及384000完整输出上限按高峰价格预留：Flash 5.304元，Pro 15.912元。预留在usage结算后释放；它不是一次请求实际花费，也不靠缩短回答来降低准入要求。

官方人民币价格快照、HTTP页面hash与计价公式见 [SERVICE_AUDIT.md](SERVICE_AUDIT.md)。每条调用另存price snapshot/hash、开始结束时间、模型/usage、成本状态、父子关系和响应路径。

## 外部服务

已审计的web_search、fetch_page、get_paper_text不调用外部收费模型，按0元外部API费用登记，不声称本地机器计算没有成本。ScholarTrace.query和其他费用上界不可核验的方法没有被当作免费调用；未执行部分见 [MCP_REQUIREMENTS.md](MCP_REQUIREMENTS.md)。

权威数据库：隔离worktree的 `.arc-validation/arc.sqlite`。逐run人类账单及trace位于 `.arc-validation/reports/`；原始模型消息为私有产物，不进入Git或本报告。
