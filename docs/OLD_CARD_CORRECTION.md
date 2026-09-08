# 旧自然卡科学修订：初轮与开发辅助后续

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

以上为初轮保留记录。后续显式开发辅助修订已完成，结果见下；不覆盖初轮原件或费用。

## 显式开发辅助后续已完成，独立验收仍失败

运行 `functional-20260908-old-natural-targeted.science` 将独立副本 `card_2e27585aa71943448ff218e97762e35f` 从 v1 修订至 v2。ARC 最终为 COMPLETED / PROMISING（experiment_required），独立 CodeX 科学验收仍不通过；这不是无辅助科学发现或未见主题测试。

主四条件与80K/200K总图数已实际修正，原四类穷尽划分未回退；但额外两格仍写+40%而非+50%。可加性新增CI落入预注册容差的限制，却把所有不落入容差都写成“未发现可辨交互”：容差[-1,1]而CI[3,5]即反例。H3把改变实例组成的分支改为未决，但同实例重计分仍被当作测量地板主导的充分证据；真实误差类型与指标敏感性仍可能解释翻转。部分真修复不能替代整卡验收。

本次24条账本调用全部SETTLED，无未结算调用，已结算 **6.615900–6.615908 CNY**；包括首任务source/quote协议失败的1.650115元上界，不重复相加。后续显式retry、修订、复核已接受，原失败与原费用保留。该数是独立子账本的已结算区间，部分来自有界估算，不冒称供应商精确账单。

精简实际前后对照与分任务成本见私有 `work/OLD_TARGETED_RESULT.md/.json`，最终科学审计见 `work/OLD_TARGETED_SCIENCE_AUDIT.md`；Windows交付同名文件及 `reports/functional-20260908-old-natural-targeted.science/` 保留ARC原报告。旧卡两个阶段和后续自然develop是不同运行，结果与费用分别报告。
