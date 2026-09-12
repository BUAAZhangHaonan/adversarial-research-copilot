# Review Audit — 2026-09-06

对照原始审阅（基线 b814b69）与修复计划（2026-09-06-review-fixes.md）的逐条严格审核。
每条结论均以当前代码为准重新取证（file:line），不依赖实现时的记忆。

状态图例：✅ 已修复并验证 · 🟡 部分实现 · ⛔ 明确不做（附理由）

## 一、事实问题（R1-R9）

| # | 问题 | 状态 | 证据（当前代码） |
|---|---|---|---|
| R1 | 审计默认放行 | ✅ | discover_runner.py:648-721 三状态+NOT_AUDITED 显式记录+集合完整性校验（:721）；:672/686/692 web失败/解析失败/未知verdict→INSUFFICIENT_EVIDENCE；`_audit_verdict` 无记录→NOT_AUDITED。测试：3 个回归（第9+gap不通过/web失败≠KEEP/垃圾输出≠KEEP）。E2E 中 audit 三值真实出现 |
| R2 | 深读排序反转 | ✅ | discover_runner.py:482 第一键 `agent_rank is None`（带 rank 优先）；混合池回归测试 |
| R3 | reviewer 反馈断链 | ✅ | chat_mode_runner.py:262 `cycle_reviewer_feedback = prior_reviewer_feedback`（所有周期）；:517 reviewer 收到自己上次意见。唯一标记跨周期回归测试 |
| R4 | 前置成果未接入辩论 | ✅ | chat_mode_runner.py:253/:1205 `_build_research_object`（FINAL_PROPOSAL/EVIDENCE_TABLE/EXPERIMENT_PLAN → [RESEARCH OBJECT] 块）；:1014/:1058 注入 proposer/skeptic 首轮。单测验证注入；E2E 中前置产物存在故代码路径活跃（提示词本身不落盘，已在实验记录中如实注明） |
| R5 | stress-test 丢证据+同模型 | ✅ | discover_runner.py:926-952 `_idea_brief` 完整候选（证据/实验/反范围/查重结论）；:967 skeptic=judge 跨模型。单测断言 brief 各字段与模型分工 |
| R6 | 空候选非法 | ✅ | discover_runner.py:1044/1054/1059 `_has_list_key`（显式空列表合法）；:300 zero_gaps_mined / no_surviving_gaps / :333 no_composable_ideas 三种一等公民出口。两个回归测试 |
| R7a | 轮内重试重跑成功角色 | ✅ | chat_mode_runner.py:279-297 round_cache（drift/proposer/skeptic 轮级缓存）；回归测试：moderator 503 重试时 proposer/skeptic 各只调 1 次 |
| R7b | 深读中断重复付费 | ✅ | discover_runner.py:490/505 arxiv_id 映射缓存；:509/:574 逐篇 note 恢复（json sidecar+md 兼容）。回归测试 |
| R7c | 历史记忆不足 | 🟡 | 核心已解决：争点表（open_issues）跨轮注入 proposer/skeptic（chat_mode_runner.py:380-408/1041-1042），替代纯 220 字符锚点作为历史机制；锚点仍保留作补充。E2E：3 轮 ledger 真实增长（1→2 issues）。未做：把完整历史轮次喂给 moderator 的重复检测（其判断依据为 ledger+本轮内容，未含前几轮全文——按审阅"把更多全文塞进上下文同样不理想"的提示，保留现状） |
| R8 | STOP 正文误判 | ✅ | rubric.py:64-77 无效即返回 None（正文不再猜测）；orchestrator.py:103-123 一次纠正重试→仍失败 parse_degraded=True+保守 CONTINUE+protocol_errors 计数；schemas.py RoundRecord.parse_degraded。E2E：6 轮 protocol_errors=0。回归测试 3 个 |
| R9 | 成本配置 | ✅ | chat_mode.yaml: min_rounds_before_stop=2、max_rounds=60；chat_mode_runner.py:493-496 真硬上限（stop_reason=max_rounds_hard_cap_N，触发后跳过 reviewer）。回归测试：judge 永远 CONTINUE 也精确停在 max_rounds |

## 二、设计建议（D1-D8）

| # | 建议 | 状态 | 证据 |
|---|---|---|---|
| D1 | 审计→重要性/证据审计 | ✅ | saturation_auditor.md 重写：`grep -c "98%"` = 0；两类依据（real_world_failure / scientific_deficit）；三值结论；"missing evidence is not proof of absence"。契约测试与 docs/prompt-contracts.md 同步 |
| D2 | 候选定向查重 | 🟡 | 已实现主体：duplicate-check stage（discover_runner.py:40/840-883）web+scholartrace 双路检索、closest_works/differentiation/novelty_verdict、增量持久化、材料进品味门（:882）。E2E 产出 6 DISTINCT/2 POSSIBLY_DUPLICATE 且被品味门理由引用。未做：审阅提到的"追踪最接近论文的引用关系"（引文图谱遍历）——需要 scholartrace 引用遍历接口，记为后续 |
| D3 | 品味门查知识增量 | ✅ | taste_judge.md 重写（knowledge_gain/decision_changed/delta_type 四分类/distinguishes_alternatives/priority 仅排序）；代码层 `problem_novelty` 引用数=0；KILL 无 kill_evidence_type 降级 PIVOT（:904）；DUPLICATE 查重证据强制 KILL。E2E：7 KEEP+1 PIVOT（PIVOT 理由为真实方法论缺陷）、0 误杀 |
| D4 | 深读抽取出条件 | ✅ | _DEEP_READ_QUESTION（:381-389）：VERIFIED CLAIMS 含条件/控制变量/未排除的替代解释/来源位置；作者自述 vs 推断标注；gap_miner 增加可比性检查（不同规模/分布=条件非冲突）。动态深读调度 ⛔（见下） |
| D5 | 有条件否决记录 | ✅ | _build_rejection_log（:1296/1324 reopen_condition；:1341 渲染）；三类出口全部落盘。回归测试（INSUFFICIENT/KILL/duplicate 三类 reopen 条件） |
| D6 | 争点表+停止语义分离 | ✅ | _parse_moderator_structured（assessment/next_action/stop_reason/open_issues，枚举校验）；next_action 驱动停止：RETRIEVE/EXPERIMENT 结束文本辩论+PENDING_ACTIONS.md+reviewer 不得重开文本周期（:487/:502）；tag 保留为渲染兼容；structured_ok 降级标记。en/zh prompt 契约同步。E2E：3 轮→EXPERIMENT 路由（对比修复前同主题 166 轮） |
| D7 | 减少双写 | ⛔ | 未实现。gap_miner.md:48 / idea_generator.md:45 仍要求"人类可读分析 + YAML"双写。理由：该改动会触碰全部 discover 提示词契约与测试，而本期 token 收益更大的重复调用问题（R7a/R7b、轮内缓存、深读恢复、查重增量恢复）已全部落地；双写问题记为独立后续项，与"prompt 打磨模块"一起做 |
| D8 | usage/成本报告 | ✅ | llm_client.py:55-74/122 中央采集（22 个调用点零改动）；COST_REPORT.md 两个 runner 落盘（discover_runner.py:213 / chat_mode_runner.py:607），MCP 只计调用次数并如实标注服务端成本不可见；usage 缺失计 0 但单独计数标记。E2E：三份真实成本报告 |

## 三、审阅中其他建议的处置

- **四.1 第一轮盲评独立性** ⛔：审阅自述"需要在 ARC 上验证，不能直接保证优于现有流程"，且 Debate or Vote 的证据要求等预算投票基线先行。记为实验项，不盲改流程。
- **三.1 动态深读调度**（结论图谱+按需定向深读）⛔：架构级改动；本期以"抽取问题升级"（D4）落地其价值前提。后续单独评估。
- **四.4 两模式内核完全统一** ⛔（按用户决策取中等深度）：共享构建块已在 chat-mode 落地（研究块、争点表、停止语义）；正式 debate 获得协议修复（R8）但保留自身契约。
- **四.2 的"proposer 可承认反例/撤回主张"角色提示词** 🟡：争点表已注入 proposer/skeptic（含"respond to these, do not re-argue settled points"），但角色 prompt 未显式增加 concede/withdraw 措辞——记入后续 prompt 打磨。
- **七 的"每次继续调用须说明如何改变下一步行动"** 🟡：next_action 路由在辩论侧实现了其核心（不再为只有证据能回答的问题继续调用）；通用的调用前信息增益论证层未实现，记为后续。

## 四、验证总况

- 全量测试 87 个全部通过（基线 b814b69 时为 65 个，本轮净增 22 个回归测试）。
- 三模式真实 E2E 各一次，记录于 2026-09-06-e2e-experiments.md（含如实注明的局限：提示词不落盘导致两处注入仅由单测验证；gap 挖掘偏保守；审计上限未在真实规模下触发——单测覆盖）。
- 审阅九项事实问题（R1-R9）全部闭环；八项设计建议 6 项落地、1 项部分（查重缺引文遍历）、1 项明确不做（D7，附理由）。
