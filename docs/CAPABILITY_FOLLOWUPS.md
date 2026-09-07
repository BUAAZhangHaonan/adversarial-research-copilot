# 后续能力需求：非 arXiv 全文获取

2026-09-08 开发评估与备选方案。只读复核验证数据库中 `arc-vnext-validation-20260907.natural_runtime_versions_v2` 的 develop 和 run 需求记录：develop 4 条、run 1 条，共 5 条，均为 `pending_user_review`，尚无已登记评估。相较首次整理新增 3 条；本文未修改数据库、调用模型或验证外部服务。

本次快照截至北京时间 2026-09-08 02:06（UTC 2026-09-07 18:06），后续运行可能继续提出需求。

## 待评估记录

| 记录 | 提出任务 | 概要 |
| --- | --- | --- |
| R1 | develop / `round1.moderator.evidence_reassessment` | 扩展 `read_paper` 的输入与获取路径，支持非 arXiv 标题、DOI 或出版社 URL；需要原文、定位、访问状态和明确失败原因。 |
| R2 | develop / `round1.retrieval.source_recheck` | 在 R1 基础上提出可复用的非 arXiv 全文/OA 副本获取能力，并要求有限尝试、版本区分和结构化失败记录。 |
| R3（新增） | develop / `round2.proposer` | 补充 PDF/HTML 正文解析、出版版本登记和明确失败码；当前仍以可得内容及常设访问限制收尾。 |
| R4（新增） | develop / `round2.moderator` | 请求 DOI/会议库页面原文获取及段落定位；明确不改变当前交由人类实验的裁决与实验预算。 |
| R5（新增） | run / `round1.proposer` | 请求 DOI/URL 正文提取，区分全文、摘要页、元数据和 snippet，并提出有界预览；明确不改变本轮科学假设判定或增加训练预算。 |

R1 完整 request ID：

```text
cap_arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.round1.moderator.evidence_reassessment.envelope.0
```

R2 完整 request ID：

```text
cap_arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.round1.retrieval.source_recheck.envelope.0
```

R3 完整 request ID：

```text
cap_arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.round2.proposer.envelope.0
```

R4 完整 request ID：

```text
cap_arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.arc-vnext-validation-20260907.natural_runtime_versions_v2.develop.round2.moderator.envelope.0
```

R5 完整 request ID：

```text
cap_arc-vnext-validation-20260907.natural_runtime_versions_v2.run.arc-vnext-validation-20260907.natural_runtime_versions_v2.run.round1.proposer.envelope.0
```

五条需求针对同一科学问题，建议合并为一个能力支线评估，保留全部原始记录。新增记录补充了 PDF 解析、连续正文定位和访问失败的区分，没有形成新的独立实现范围。目标文献是 PRL 2022 的 DOI `10.1016/j.patrec.2022.04.008`，以及 SIBGRAPI 2020 的 IEEE document `9266023` / SBC 文章页 `14135`；不同出版形态须区分，不能仅凭相似标题互换。需要核验全文是否已经包含当前研究卡所提出的等价实验，从而决定保留、收窄或重审研究主张。

Agent 记录称现有 `read_paper` 仅接受 arXiv ID/URL，其他路径遇到 403、反机器人页面、镜像故障或超时。这些是需求中的历史运行描述；本文未重新探测相关网站。R2 所列 OA 服务的接口、覆盖、权限、费用及新依赖尚未评估，不能视为已确认的可行方案。包装接口或查询 OA 索引不能保证获得被拒绝访问或付费墙后的正文；索引未命中也不能证明不存在开放副本。

## 本次收尾边界

本次必须修复的是协议把正常纠错、有效补证请求或明确撤回错误证据阻断的问题。moderator 新 issue 的请求交接、最终裁决请求保留，以及 `source_recheck` 元数据撤回 gate 已由相应修复处理；其中最后一项对应 `1aa8107`。develop 已完成，run 正在卡片 v7 上继续争点依据纠正，最终状态以主流程验收报告为准。

新增全文获取通道属于后续可选支线。只要最终研究卡如实保留全文未核验的搜索限制与重新审查条件，就不应为追求一次完整全文获取而无限重试或扩大本次实现。访问失败只能关闭本次有界检索尝试，不能关闭“该全文是否含等价实验”的科学问题，也不能据此宣称新颖性已确认。

`read_record` 每次 64000 字符及相应分页、预算、恢复验证已经完成，不列为待办。本次也不新增无意义的人工哈希校验；任何后续正文接入复用既有来源记录机制即可。

## 给用户的候选决策

问题一：目前两篇全文未获取，如何推进研究判断？

- **推荐：保留限制并完成当前有界流程；需要进一步确认时，由用户提供合法取得的 PDF，注册原始来源后定向复核。** 无需先开发新检索系统；仍须确认论文版本与正文覆盖。
- 本次即开发非 arXiv 获取通道。需要另行评估实现范围、成功样例与失败样例、依赖和预算；不能承诺解决现有网站的访问障碍。
- 等待公开副本或镜像恢复后，由用户触发一次有界复核。成本低，但没有确定完成时间。

问题二：是否把 R1–R5 合并为正式能力支线？

- **推荐：登记为待用户评估的一个支线；若非 arXiv 文献获取反复影响抽卡质量，再实施。** 第一阶段先核实 DOI/URL 解析、可合法访问副本的发现方式、原文解析和结构化失败输出，不预先接入所有候选服务。
- 暂不实现，沿用现有检索工具与用户提供正文。保留需求记录，之后可重新评估。
- 直接实施多个全文/OA 服务集成。范围和维护成本更大，当前证据不足以推荐。

如后续获准实施，验收至少包括一个确实返回原文的样例、一个拒绝访问的样例、摘要与正文不混淆、版本与出处可追溯、尝试次数和费用可见，以及失败时保留科学不确定性。超出现有授权范围的付费服务或预算须另行明确；当前收尾继续使用已经批准的剩余余额，不重复申请阶段额度。

R3 所提“失败不计费”不能预设为保证，应按真实服务计费和实际模型用量记录；获取失败也可能已经消耗请求与模型费用。向作者发送邮件仅作为用户可选择的人工渠道，本文不授权或执行联系。

正式服务中，Agent 仅提出需求，用户负责评估和实施。本次 CodeX 的整理和建议属于开发阶段，不构成生产环境里的自动审批、执行或扩容。
