# 运行前费用预估与账户余额

当前默认配置名和实际请求名统一为 `deepseek-flash`。官方于 2026-09-10 将它对应到 DeepSeek-V4.1-Flash；版本来源仍记录在已选价格快照，旧 run 的模型配置和历史费用不会重写。

每次新阶段或恢复运行，在创建模型 runtime 之前显示 `run_preflight`：预计人民币范围、分阶段假设、余额查询状态和必要告警。已完成、取消或因范围变化停止的 run 不再查询余额、不创建模型 runtime，不会因为现在没钱而把历史完成状态改成暂停。

## 预计费用怎么算

- 当前实际 API 模型有已 ACCEPTED 的同类语义任务时，将这些任务的原始输入、输出与缓存 usage 按当前价格重新计算。不同角色只按对应阶段分组；旧 Pro 费用、模型自报成本和未完成任务不作为样本。
- 经验区间使用观测任务的低端成本 × 0.75 到高端成本 × 1.5，另保留峰谷、缓存未知的计价差异。样本数量和该假设随结果一起展示；少量样本不能保证未来费用。
- 没有同模型已完成样本时，使用 `preflight.TOKEN_ASSUMPTIONS` 中明确的整项任务输入/输出 token 区间。这是跨全部工具回合的任务用量假设，不是单次生成上限，不会限制或截断模型输出。
- discover 按计划构思次数、一次共享调查、对应价值初筛、0 到 N 个候选 CHECK，以及整阶段一次 writer.POLISH 估计。develop/run 各按一项预研和一次润色估计。恢复时扣除已接受任务，已润色不再预留一次润色。
- 这不是保证、费用硬上限或应花满额度。提前停止可能更便宜；检索深度、材料长度、纠错和外部收费工具可能让实际费用超过范围。外部工具费用未计入本模型 token 估计。

仍保留原有价格与预算准入规则。完整请求最坏预留（当前模型为 4.304 元）不是预计单次消费，也不会拿它乘任务数冒充经验估计；默认生产阶段预算仍为 20 元。

## 余额查询和失败

依据[官方余额 API](https://api-docs.deepseek.com/api/get-user-balance/)，使用现有配置凭据调用免费只读 `GET /user/balance`。凭据、Authorization 和错误响应正文不会写进预估或日志。当前人民币单价及峰谷规则来自[官方价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)，本轮直接读取核对，未以搜索缓存或页面哈希代替检查。

余额低于预计范围只告警，不要求新批准；网络错误、缺少凭据、异常响应或不可比较的币种不阻止原有执行。仅当供应商明确报告账户不可调用，或明确人民币余额已经不大于零时，在付费请求之前暂停为 `provider_wallet_unavailable`。充值后可恢复，账本费用不清零。

完整余额结构只保存在私有 run state 与 `artifacts/runs/<run>/preflight/*.json`。控制台只显示必要总额，不展示赠送/充值构成。项目公共报告与版本库不应复制真实余额记录。

## 程序接口

```python
from arc.preflight import estimate_stage, prepare_run_preflight, display_preflight

# 纯本地：适合先计算一批阶段的情景费用；不会查询余额或修改账本。
estimate = estimate_stage(settings, prices, store=store, ledger=ledger,
                          mode="discover", draws=5, polish=True)

# 在每个阶段开始前调用：只读查询余额，保存私有预估记录；不会预约费用。
record = await prepare_run_preflight(store, ledger, run, settings, polish=True)
print(display_preflight(record))
# record["wallet_exhausted"] 为真时，批量驱动应停止购买新请求。
```

预估支持同一个共享父账本下的批量阶段，不会创建额外账户、改变额度、重复记账或自动续费。
