# 固定材料质量对照

汇总时间：2026-09-07T10:40:16.144374+00:00。

本对照的自动评价仅可作为初步审查；实际是否完成逐组列出。它不是专家gold label、实验证明或ARC质量改善的定论。
各候选使用同一冻结材料、原文与边界，禁用在线补证；初始上限20元，分割direct-Pro经用户明确授权追加至25元。限额与实际花费均逐项列出，不能视为严格等成本对照。
在线检索能力另由真实任务trace评价。未完成结果不会纳入成功对照。
材料收集、候选、失败及匿名评价的全部费用均计入原100元父账本；完整分项见[COST_REPORT](COST_REPORT.md)。

## 固定场景的合成到真实视觉泛化中，如何区分材质/光照随机化与几何变化对模型错误的影响

状态：incomplete；材料SHA256：`8896f127a5567c3cd2de9c99c36442fa83347864f9bb61a0af8f508f41afbd1a`；排序种子：20260907。
来源run：`arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover`；152条来源记录、19条证据，来源记录数不等同独立论文数。

| 方案 | 执行状态 | 是否产出卡 | 正式selection | 授权限额（元） | 实际usage计价下界/上界（元） | 停止原因 |
|---|---|---|---|---|---|---|
| ARC | PAUSED_PROTOCOL | 无 | 尚无 | 20.000000 | 1.808136 / 1.808138 | INVALID_OUTPUT_AFTER_REPAIR |
| direct-Pro | PAUSED_PROTOCOL | 无 | 尚无 | 20.000000 | 1.264327 / 1.264328 | unknown_evidence_id |

没有已完成的匿名评价；不能据此宣称哪方更好。

原始结构化结果：隔离工作目录的 `.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/comparison.json`。

## 拥挤小目标实例分割中，边界错误与实例合并错误是否需要不同的测量与干预

状态：incomplete；材料SHA256：`706a5492a913d4f11357f73c6d45fbef22cf4b7290ec86f4e3cdcc9343e799bd`；排序种子：20260907。
来源run：`arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover`；276条来源记录、18条证据，来源记录数不等同独立论文数。

| 方案 | 执行状态 | 是否产出卡 | 正式selection | 授权限额（元） | 实际usage计价下界/上界（元） | 停止原因 |
|---|---|---|---|---|---|---|
| ARC | PAUSED_EXTERNAL | 无 | 尚无 | 20.000000 | 1.323994 / 1.323996 | frozen_material_blocked |
| direct-Pro | COMPLETED | 有 | MAIN_REPORT | 25.000000 | 7.101934 / 7.101937 | frozen_material_comparison |

没有已完成的匿名评价；不能据此宣称哪方更好。

原始结构化结果：隔离工作目录的 `.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover/comparison.json`。

## 多模态冲突理解中，如何在受控观察下区分模态可靠性变化与标签歧义

状态：incomplete；材料SHA256：`8cf9dd279cc35cde3f3eedf36830ec8d07eec5403ddbbd6c2d43c1e24554d293`；排序种子：20260907。
来源run：`arc-vnext-validation-20260907.materials.conflict_holdout`；9条来源记录、15条证据，来源记录数不等同独立论文数。

| 方案 | 执行状态 | 是否产出卡 | 正式selection | 授权限额（元） | 实际usage计价下界/上界（元） | 停止原因 |
|---|---|---|---|---|---|---|
| ARC | PAUSED_PROTOCOL | 无 | 尚无 | 20.000000 | 0.451487 / 0.451489 | evidence_request_claim_id_not_supplied_to_task |
| direct-Pro | COMPLETED | 有 | MAIN_REPORT | 20.000000 | 1.989082 / 1.989085 | frozen_material_comparison |

没有已完成的匿名评价；不能据此宣称哪方更好。

原始结构化结果：隔离工作目录的 `.arc-validation/artifacts/evaluations/arc-vnext-validation-20260907.materials.conflict_holdout/comparison.json`。
