# 当前费用报告

账本快照：2026-09-07T18:57:22.397577+00:00。唯一父账户 `arc-vnext-validation-20260907`，总限额 285.562384 元。

已结算估计 **84.810721–84.960337 元**；预留 0.000000 元，未知调用 0，剩余 200.602047 元。

包含所有历史失败、旧质量对照、协议纠错和本轮收尾调用；没有重置历史花费。调用数按账本记录统计，包括失败或未发送记录，不等于付费请求数。限额不是实际支出，子账户限额不相加作为父级授权。以下逐行只统计该账户自身调用，父级总计只汇总一次。

| 账户（省略父账户前缀） | 限额/元 | 调用数 | 已结算下界/元 | 已结算上界/元 | 预留/元 | 未知 |
|---|---:|---:|---:|---:|---:|---:|
| 父账户自身 | 285.562384 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
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
| ARC_VNEXT_VALIDATION_V3.discover.comparison.ARC | 285.562384 | 9 | 7.125499 | 7.125507 | 0.000000 | 0 |
| ARC_VNEXT_VALIDATION_V3.discover.comparison.direct-Pro | 285.562384 | 3 | 7.101934 | 7.101937 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.discover.comparison.ARC | 285.562384 | 8 | 3.158372 | 3.158377 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.discover.comparison.direct-Pro | 285.562384 | 5 | 3.799029 | 3.799034 | 0.000000 | 0 |
| materials.conflict_holdout | 20.000000 | 50 | 1.328487 | 1.328501 | 0.000000 | 0 |
| materials.conflict_holdout.comparison.ARC | 285.562384 | 8 | 1.474023 | 1.474030 | 0.000000 | 0 |
| materials.conflict_holdout.comparison.direct-Pro | 285.562384 | 3 | 1.989082 | 1.989085 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.develop | 20.000000 | 27 | 0.688819 | 0.688825 | 0.000000 | 0 |
| explicit_input_schema_v2.run | 20.000000 | 16 | 0.622656 | 0.622660 | 0.000000 | 0 |
| explicit_input_schema_v2.develop | 20.000000 | 72 | 1.704536 | 1.842874 | 0.000000 | 0 |
| explicit_input_schema_v3.run | 20.000000 | 39 | 0.294770 | 0.294781 | 0.000000 | 0 |
| natural_tool_correction_v1.develop | 20.000000 | 60 | 1.679891 | 1.679914 | 0.000000 | 0 |
| natural_runtime_versions_v2.develop | 285.562384 | 198 | 17.484811 | 17.484877 | 0.000000 | 0 |
| natural_runtime_versions_v2.run | 285.562384 | 39 | 7.594878 | 7.594891 | 0.000000 | 0 |
| materials.conflict_holdout.comparison.evaluator | 285.562384 | 1 | 0.302422 | 0.302423 | 0.000000 | 0 |
| ARC_RENDERING_VALIDATION.discover.comparison.evaluator | 285.562384 | 1 | 0.672039 | 0.672039 | 0.000000 | 0 |
| ARC_VNEXT_VALIDATION_V3.discover.comparison.evaluator | 285.562384 | 1 | 1.213653 | 1.213653 | 0.000000 | 0 |

总调用数：1830。模型请求分布：{"deepseek-v4-flash": 655, "deepseek-v4-pro": 93}；语义调用均为 max。

金额为实际 usage 按冻结价格快照复算或已审计工具上界，不是供应商逐请求人民币发票。区间保留缓存明细、峰谷和舍入不确定性；reasoning 不重复计费。完整输出准入预留在请求结束后结算，不将预留当成实际消耗。

真实运行和科学结论见 [MASTER_STATUS.md](MASTER_STATUS.md)。
