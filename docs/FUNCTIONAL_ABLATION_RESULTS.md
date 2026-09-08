# 功能消融：r1已完成，r2在途

`functional-20260908-ablation-r1` 于2026-09-08 19:45:23 UTC完成A–E和双序匿名评价。**新审查确实检出旧审遗漏，并推动局部实改；最终E仍未通过独立科学核对。** 本轮不能证明ARC已优于直接Pro，也不能从单次A/B/C输出判定构思步数或模型分工的普遍优劣。r2于19:46 UTC启动，尚无完成结果。

## 比较对象与输入

两轮使用同一“长链推理提前停止”原题、四项用户边界、四篇原文与14条登记证据；无在线检索工具。A是当前Pro连贯CONCEIVE，B是当前Pro的FRAME/NEXT_DRAW/COMPOSE，C同样分步但构思由Flash承担；ABC使用相同旧Pro novelty/selector审核。D对A的同一候选作新科学审查、不修订；E复用A候选与D初审，执行一次必要修订并复核。所有实际语义请求为max。

19:47 UTC只读直接比较确认：两轮manifest材料与条件定义相等，current提示词38文件、legacy提示词35文件分别逐字相等，未使用哈希。current与legacy本来是两套不同设计，不要求彼此相等。r1实际任务加载文本均对应自己的冻结phase。r2完成后仍需核对其所有实际任务与完整结果，不能以静态输入一致代替执行完成。

r1的A/D正文直接相等；E复用review与D保存cycle review直接相等，D/E初审review_target、原题、mandate、sources、evidence均相等，E没有额外初审模型调用。seed 20260908与r2的20260909只用于匿名呈现顺序，**不是模型采样seed或确定性复现承诺**。自动评价看见相同的A/D卡，不能由卡片偏好推断两套审核本身哪个更好。

## r1科学结果

独立A/B/C清单在读取各自旧审核前形成；D/E与其对照，反馈没有注入这些模型任务。它们是CodeX开发审计，不是人类研究者的价值终审。

| 条件 | ARC实际结果 | 独立核对与比较边界 |
| --- | --- | --- |
| A：Pro连贯＋旧审 | MAIN_REPORT / PROMISING，无修订 | 最后正确点之后的coverage反向；当前安全退出与未来漂移预测混淆；非显著不能证安全。旧审读到先例、提出密度匹配，但未改正文、未拦核心错误 |
| B：Pro分步＋旧审 | MAIN_REPORT / PROMISING，无修订 | 停止模拟用了当前正确的gold门；ever-flip与终态标签混用；有限预测阴性不足以支持改换研究路线。补强基线意见没有解决这些缺口 |
| C：Flash分步＋旧审 | LEAD_ONLY / NEEDS_EVIDENCE，无修订 | 01vs10可仅由当前状态完美区分，观察窗/前向标签错位；标量输出不证明缺方向信息。LEAD_ONLY实际因为未读近邻的新颖性前置，不能计作检出这些科学错误 |
| D：A同稿＋新审 | revise / substantial，4项repairable | 自主找出coverage时间窗、具体原文组合不匹配、成本展开和抽取器声明问题；部分修法又把非连续正确点当区间、混用prefill/decode吞吐 |
| E：A同稿＋D初审＋修订复核 | v2实际保存，retain / substantial，4项resolved、无新finding | 内部oracle恒等式与离线抽取器声明真修；初始覆盖窗和成本拆项改善，但非连续性、固定64token检查次数/吞吐错误仍在，核心机制及非显著安全推论未修 |

D/E模式的run.assessment为null，表中如实使用ScientificReview的action/value，不补写PROMISING。E的接受修订提案于19:31出现，v2于19:36:35 UTC才实际保存；最终recheck接受不等于独立科学通过。新审不是完全无用，但修掉最初反例并不能保证修法一般成立；E变长、费用提高或自动偏好E也不能代替这一检查。

## 实际费用与时间

18个模型调用全部SETTLED，无未结算调用；费用 **10.081634–10.081649 CNY**，包含A–E及judge，不含父账户其他历史支出。首次CLI漏传`--env-file`造成的0调用/0费用启动错误另存 `work/ABLATION_R1_AUTH_STARTUP_FAILURE.md/.json`；恢复同一实验ID，没有重置已付费结果。

| 条件 | 实际模型调用 | 已结算上界CNY | 完成请求时长之和（秒） |
| --- | --- | ---: | ---: |
| A | Pro×3 | 1.854402 | 925.795550 |
| B | Pro×5 | 2.618193 | 875.858332 |
| C | Flash构思×3＋Pro旧审×2 | 1.842123 | 1109.204558 |
| D | Pro新初审×1 | 0.833804 | 515.782167 |
| E增量 | Pro修订＋复核×2 | 1.578218 | 618.664322 |
| 双序judge | Pro×2 | 1.354909 | 525.331723 |
| **总计** | **18** | **10.081649** | **4570.636652** |

时长来自每次模型请求实际start→end，不使用任务created→updated。首请求18:29:02.195496到末响应19:45:21.946163的窗口为4579.750667秒，包含约9秒请求间间隙；初次0调用凭据停顿在首请求之前，不算付费请求时间。这不是控制服务负载、输出长度的模型延迟基准。

**E完整研究链成本为3.132330–3.132334 CNY**：A.conception 0.720312＋D初审0.833804＋E增量1.578218（均列上界）。没有把A旧审、B/C、judge加进E链；也不能只拿E增量1.578218冒充整条链费用。真实调用与费用逐条见 `work/ABLATION_METHOD_COST_AUDIT.json`，失败调用如有费用亦按唯一call_id计入，原件不删。

## 两序匿名评价

| candidate编号 | 正序 | 交换序 |
| --- | --- | --- |
| 1 | C | B |
| 2 | A | E |
| 3 | D | D |
| 4 | E | A |
| 5 | B | C |

正序preference为null，uncertainty明确表示任务未明确要求偏好，因此不宣布赢家；交换序主动偏好candidate_2，即E。**不是赢家反转，也不是“两票E”**。差异可能涉及随机性及对可选偏好请求的理解，不能仅归因于顺序。两序都识别A/D同稿；实际findings及独立审计比可选排名更有信息。

交换序原文写 `candidate_3/4`，指D/A；现离线导出只替换完整`candidate_N`，会显示`D [candidate_3]/4`。其中裸“4”仍是匿名candidate_4=A，不是名为“system4”的新条件。完整原文和映射保留，不为了补一个排名再调用模型或改变在途比较输入。

## 原件与未完成项

私有 `work/functional-20260908-ablation-r1-ablation.md/.json` 为完整候选、审查、E变化和双序结果；`work/ABLATION_METHOD_COST_AUDIT.md/.json` 为只读方法/费用补充，r2在途部分明确pending。Windows交付已同步这些文件及 `ABLATION_R1_A_INDEPENDENT_AUDIT.md`、`ABLATION_R1_B_INDEPENDENT_AUDIT.md`、`ABLATION_R1_C_INDEPENDENT_AUDIT.md`、`ABLATION_R1_DE_INDEPENDENT_AUDIT.md`、`ABLATION_R1_COUNTEREXAMPLES.json`。未公开全部论文正文、reasoning或数据库。

r2仍待全部条件、双序评价与独立核对完成，再比较重复中的稳定性；目前不报跨轮胜率或质量提高。r1新增10.081649元与此前已完成73.165122元合计83.246771元，**不包含在途r2**，不是父账户总花费或剩余余额。
