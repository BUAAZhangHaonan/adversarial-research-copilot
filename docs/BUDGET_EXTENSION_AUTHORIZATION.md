# 三个账户的预算追加授权

用户明确回复：“允许各追加 5 元，总额仍不超过 100 元”。主线程于2026-09-07 08:39:14.754059 UTC在g203隔离worktree调用BudgetLedger.add_budget，完成以下三项追加：

| 账户（前缀均为arc-vnext-validation-20260907） | 原限额 | 追加 | 新限额 |
|---|---:|---:|---:|
| ARC_RENDERING_VALIDATION.discover | 20元 | 5元 | 25元 |
| explicit_input.develop | 20元 | 5元 | 25元 |
| ARC_VNEXT_VALIDATION_V3.discover.comparison.direct-Pro | 20元 | 5元 | 25元 |

父账户总限额仍为100元，生产默认阶段限额仍为20元；其他阶段没有获得追加授权。以上是允许的账户限额，不是新增实际支出，也不表示增加父账户总额。后续请求仍须通过阶段与父账户共同准入，继续按实际usage结算。

精确账户清单来自 `work/pending-budget-approval.json`；用户回复、执行时间、授权理由及三个实际应用结果保存在 `work/approved-budget-extension.json`。前者的awaiting状态是提问时历史记录，不能覆盖后者已经明确授权并执行的结果。账本 `budget_accounts` 保存实际限额，`budget_authorizations` 保存初始和追加授权；历史调用与费用没有重置。

`work/render_cost_report.py`以只读SQLite事务读取实际账户限额、调用及授权记录，生成COST_REPORT与费用JSON快照。报告分别列出限额、已结算支出、预留与授权，不用默认20元代替三个账户的25元限额。快照保留批准记录及其hash；本次文档与脚本编辑没有再次追加、发起模型调用或修改远端。
