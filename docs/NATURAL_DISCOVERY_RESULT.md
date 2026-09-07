# 自然发现阶段：一张主卡，第二次机会停止

`arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover` 已完成自然发现阶段。它保留一张 `MAIN_REPORT` 卡片；第二次抽卡机会的 NEXT 返回 `STOP`，最终状态为 `COMPLETED / no_distinct_direction`。这证明本次发现、筛选、停止和报告链走完，不代表人类认可了研究价值，也不代表实验结论成立。

本记录只读已保存的 SQLite 公共结构化结果、工具轨迹和报告文件。没有读取或输出私有 reasoning，没有调用模型、MCP 或新增原文下载，没有改动研究状态。下面的 selector 和 NEXT 理由属于模型产物；本记录没有代替它们重新判决。同卡 develop 已启动，其后续结果不在本记录范围内。

## 实际主卡

- 卡片：`card_52bce58017164c2b9594c418eb0cac7b`，版本 `1`。
- 标题：固定场景合成训练中材质/光照轴与几何轴的正交注入归因：T-LESS上的2×2+锚点格与按歧义/度量条件化的错误判定协议。
- 正式 selection：`MAIN_REPORT`；assessment：`PROMISING`；模型建议的 next_action：`HANDOFF_EXPERIMENT`。该建议不等于已开展实验。
- 主贡献类型登记为 `new_method`，具体是一套归因和判读协议，不是已经验证的新渲染器、训练算法或评价指标。

方案以 T-LESS 和 BlenderProc4BOP 为一个明确设置。它把材质、BRDF、纹理及光照随机化范围作为外观轴，把姿态、相机覆盖、摆放和遮挡作为几何轴。在固定真实测试集、相同训练预算下，比较 2×2 条件和默认锚点。读数包括召回、实例身份混淆、连续姿态误差，以及对称性、可见性分层和 MSSD/MSPD/VSD 度量。它希望区分两轴效果可加、存在覆盖相关交互、或者结论受歧义和度量选择影响三种情况，从而决定下一步调整哪种合成数据因素。

这些条件和预期结果仍是实验设计。卡片给出的训练 800–2600 GPU 小时等资源数字是估算，没有吞吐或效果实测。

## Selector 为什么留下它，哪里最容易失败

Selector 认为各假设分支都会改变后续决策：可加效果支持依次缩小单轴范围；交互要求给出条件化归因；度量混淆则要求先检查评价方式。它还认为，已查近邻虽然覆盖相关随机化或评价问题，仍没有完全覆盖卡片提出的 6D 错误分解、歧义分层和交互判读组合。这是已检索范围内的判断，不是“首次提出”的证明。

Novelty 已找到更近的 DIMO（arXiv:2211.16066，姿态×光照设置和真实 2D Mask R-CNN AP）及 SADGE（arXiv:2605.22467，度量相关性）。Selector 要求下一版把它们加入 `closest_work_delta`。本次保存的 v1 尚未完成该更新；不能把 selector 看过近邻等同于卡片近邻表已经补齐。

最致命的前提是：选定 BlenderProc 版本和 T-LESS 资产能否独立控制外观轴与几何轴，尚未实际验证。Selector 明确指出，如果官方模块开关和最小自定义管线都无法做到，协议前提就不成立，需要重定几何因素或放弃这个设置。

另有两组会影响可行性的限制：

- 合成数据单独训练的配方尚未固定。引用的公开 CosyPose 配方涉及合成加真实数据；低召回或种子噪声大于因素效应，都可能让交互无法识别。
- BOP-D 标注可得性、当前设置下 VSD 的实际支持、训练与测试姿态覆盖量化尚未落实。缩小外观随机化范围也不自动等于更接近真实材质和光照。

已有的 [RENDERING_EVIDENCE_REVIEW.md](RENDERING_EVIDENCE_REVIEW.md) 记录了较早 shared investigation 材料的协议失败快照和科学范围问题，包括单轴归因、训练条件与部分正文覆盖的限制。该文中的历史暂停不是本 run 的当前状态；本次 `MAIN_REPORT` 也没有自动消除其中的科学限制。本记录没有重做全文审查或将这些审查意见注入模型。

## 为什么没有第二张卡

第二次机会的 NEXT 认为，在当前范围和已有材料下，没有足够不同且有依据的新方向：重复 T-LESS 外观×几何组合属于同一贡献；只换 HB/ITODD 或改成 2D/mask 读数，不足以产生独立的新知识；进一步拆分几何、外观、度量和模型不变性，主要是第一张卡的控制或扩展，并依赖它尚未得到的实验结果。测试端光照、布局变化或线索冲突则超出当前任务范围。

这一判断有明确检索边界：draw2 保存了 5 次 `lookup_archive` 和 2 次 `search_web`；档案查询均为 `limit=8, offset=0`，没有翻页。因此 `no_distinct_direction` 表示本次有界查找选择停止，不表示研究领域没有其他方向。新实验结果或新的已核查材料仍可能形成不同方向。

## 次数、状态和费用

| 项目 | 已保存结果 |
| --- | --- |
| Campaign | `campaign_f41ce4c25f514bd9b28867854dcad96c` |
| 最大抽卡次数 / 已开始次数 | `5 / 2` |
| Draw 1 | 保留上述 v1 主卡；开始于 `2026-09-07T07:48:19.149639+00:00` |
| Draw 2 | NEXT 选择 STOP，没有第二张卡；开始于 `2026-09-07T09:27:31.566358+00:00` |
| 完成时间 | 最终 NEXT 响应保存于 `2026-09-07T09:34:26.640818+00:00`，北京时间 17:34:26 |
| Run 状态 / 停止原因 | `COMPLETED / no_distinct_direction` |
| 本验证阶段预算上限 | 25 CNY |
| 已结算费用区间 | **8.897677–8.897731 CNY** |
| 调用数 / 状态 | 199 次，全部 `SETTLED`，预留金额 0 |
| 按费用上界计算的余额 | 16.102269 CNY |

费用只属于这个 discover 阶段，不包含同卡正在运行的 develop，也不是所有验证任务的总费用。第二次 NEXT 已占用一次机会；不能把“一张成卡”写成“只抽了一次”。剩余三次机会没有使用。

完成后的 run 焦点字段 `card_id/card_version/assessment` 为 null；卡片和正式 selection 仍分别保存在 `cards` 与 `selections` 表中，不能把这些焦点字段解释为没有卡片。

## 可复核路径与 SHA256

远端根目录：`/home/g203/zhanghaonan/arc-vnext-20260907/`。数据库：`.arc-validation/arc.sqlite`。以下数据库 hash 对相应行的 `data` 原始字符串按 UTF-8 计算；文件 hash 对原始文件字节计算。

| 数据库对象 | SHA256 |
| --- | --- |
| 上述 run 的 `runs.data` | `c745b1ee34689c66d66f82b2fdfe58d29351c261d718192211a20117c9bb205a` |
| 上述卡片 v1 的 `cards.data` | `7383353c4876a14efbab7fd746cec941e340c790a6dedcf361be60c50310f7b1` |
| 上述卡片 v1 的 `selections.data` | `c40fe37dd5bb1864a4451407bb2ba2a6725037f76f6456e902524792ecd5d3c8` |

任务 artifact 的公共前缀为：

`.arc-validation/artifacts/runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/tasks/`

| 已接受任务 | 前缀之后的状态文件 | SHA256 |
| --- | --- | --- |
| `.draw1.selection` | `eda010dd42c2c558fa811ba2b98e88f81530027f8e869955f6b56222c5398dc8/states/fc9c14c1cf9b454db3947b406b2689ee.json` | `9c2c99a88f03bd7d6046556e66ec2fa50560d89592c0963470390aebf7765b3e` |
| `.draw2.next` | `b52c4b640910b8ec3c30e7dafc7c5f994e801905c70cce27f30427462dbc7081/states/17462bf842de4c278b9be5b72e05ff68.json` | `4681fc91aa13bbe6d514053a3ea14ae355df26a2588d2ca0d54ea97ac79c5e89` |

任务名称均以完整 run ID 为前缀。Selector 保存的工具轨迹有 7 次 `read_record`、2 次 `read_web`；上述 NEXT 的轨迹计数见停止理由。记录状态文件路径用于复核，不需读取私有 reasoning。

报告公共前缀：

`.arc-validation/reports/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/`

| 报告相对路径 | SHA256 |
| --- | --- |
| `REPORT.md` | `1cf462d01a2c3b37bcb29a93124760d4c473cf4728385b303a6be3189db48a9d` |
| `cards/card_52bce58017164c2b9594c418eb0cac7b/v1.md` | `37b0335ddb79e9b7a3a43ecab87d16d819751b72d3effa02470e0615db056929` |
| `PROMPT_TRACE_INDEX.md` | `0e7e75a23715c4bb158d31de46213dbf72df2cb68cdd6e98abe661e03ceb0990` |
| `COST_REPORT.md` | `05c911180eb4e13766cf4ba16daf359d19b620586e851dc083fa897f809d9109` |
