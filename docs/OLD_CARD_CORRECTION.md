# 旧自然卡科学修订：初轮结果

**已知目标错误已实际修复，整张卡尚未通过最终验收。** 本次不是未见主题测试，也没有训练模型或执行研究实验。

| 项目 | 记录 |
| --- | --- |
| 历史原件 | `card_52bce58017164c2b9594c418eb0cac7b` v7 |
| 历史最终运行 | `arc-vnext-validation-20260907.natural_runtime_versions_v2.run`，COMPLETED / PROMISING |
| 本轮独立运行 | `functional-20260908-old-natural-v7.science` |
| 当前修订副本 | `card_4aa11de0acd4448c951f583ea90f48d3` v3；原 v7 及历史判断保留 |
| 本轮结果 | COMPLETED / **NEEDS_EVIDENCE**；`scientific_revision_unresolved` |
| 本轮费用 | **5.691864 CNY**，56 条账本调用记录；按已结算上界，不是父账本累计 |

原题仍是固定场景合成到真实视觉泛化中，如何区分材质/光照随机化与几何变化对模型错误的影响。本轮走独立科学审查、定向修订与复核，不进入旧辩论流程。

## 已保存的真实修复

`minimal_test.measurements[0]` 原先写道：

> 全实例联合错误分解（确认性主统计量）：检测失败份额+ID混淆份额+ID正确-位姿超阈份额=1

副本当前明确：每个真实 GT 实例进入检测失败、检出但 ID 混淆、ID 正确但位姿超阈、ID 正确且位姿达标四类之一；四类互斥且穷尽、份额之和为 1。前三类错误份额之和是条件错误率，不能恒等于 1。

同一修复已同步到六处实际文本：`contribution.knowledge_increment`、`method.simplest_path`、`method.necessary_components[3].component`、`minimal_test.intervention`、`minimal_test.controls[12]`、`minimal_test.measurements[0]`。最终 Agent 用全对与全错两个极端例子再次检查了划分。

官方 `eval_bop24_pose.py` 的输出键枚举也已改正：补列 `bop25_mAP_mm`，并将 `bop24_average_time_per_image` 明确为计时字段。该修正由最终补证审查读取已缓存的官方代码尾部复核，定位来源 `src_932eee86d8f0402db9389068b21f2d3e`；它不等于研究实验已经执行。

## 尚未解决：区分模型发现与开发反馈

**最终 Agent 补证审查发现的缺陷**：`pressure.science.support_review` 提出 `finding_condition_count_5`。正文实际只有 C00、A-、G-、A-G- 四个条件，却在干预与方法中写“五个”，并把每条件约 20K 图的渲染总量算作 100K、升级到每条件 50K 后算作 250K。按当前四条件定义，应分别为约 80K、200K；种子重复不是新增训练分布。该问题尚在当前副本中，Agent 最终动作是 `revise`，系统因此保留 NEEDS_EVIDENCE，没有用价值判断 `substantial` 冒充科学问题已关闭。

**CodeX 独立开发审计的额外反馈**：可加性结论的适用范围，以及把分层/度量异质性进一步解释为测量伪影的推论，仍需收紧。它们不属于上述最终 Agent 已发现或已解决的缺陷，尚待带显式反馈的定向修订与复核。

下一轮尚未执行。最终验收需同时核对条件计数与资源算术、相关推论的实际修改及审查结果；仅看到新版本、`resolved` 或 COMPLETED 都不能算整卡通过。初轮原件和费用记录将保留。
