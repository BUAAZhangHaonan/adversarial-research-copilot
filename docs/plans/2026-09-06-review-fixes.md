# Review Fixes Plan — 2026-09-06

对照外部审阅（基线 `b814b69`）的修复计划。审阅条目编号：

**事实问题（R 系列）** — 已在核实阶段逐条确认属实：
- R1 discover 审计默认放行（>8 gap 绕过审计、解析失败补 KEEP、web 失败仍裁决）
- R2 深读排序第一键反转（无 agent_rank 的论文优先消耗预算）
- R3 chat-mode reviewer 反馈未传入后续周期（连续运行中从未生效）
- R4 chat-mode 前置成果（FINAL_PROPOSAL/EVIDENCE_TABLE/EXPERIMENT_PLAN）未接入辩论
- R5 discover stress-test 丢证据且 proposer/skeptic 同模型
- R6 空候选（`gaps: []`）触发重试后报错，非一等公民
- R7 历史记忆不足（220 字符锚点支撑不了重复检测/收敛判断）；轮内重试重跑已成功角色；深读中断恢复 stage 粒度重复付费
- R8 正式 debate STOP 正文子串误判（"Do not STOP" → STOP）
- R9 成本配置：min_rounds=20 强制最少 20 轮；max_rounds 是软目标，实际上限 10×20=200 轮

**设计建议（D 系列）**：
- D1 saturation audit 改"重要性与证据审计"，删 98% 通用规则（审阅二.1）
- D2 候选形成后定向查重（同义表述/相同机制/邻近领域检索最接近工作）（二.2）
- D3 品味门查知识增量而非句式；删 novelty<=2 硬杀，分数仅排序（二.3）
- D4 深读抽取升级：验证条件/控制变量/替代解释/来源位置（三.1）
- D5 有条件否决记录（对象/条件/证据/reopen_condition）（三.5）
- D6 chat-mode 争点表 + 停止语义分离（assessment/next_action/stop_reason）（四.2/四.3）
- D7 discover 输出结构化为主，减少人类可读+YAML 双写（五）
- D8 LLM usage 中央采集与成本报告；MCP 只计调用次数并如实标注（七）

**用户决策**：chat-mode 中等深度改造（研究块注入+轻量争点表+停止语义分离，保留 tag 兼容）；收敛参数 min_rounds_before_stop=2、max_rounds=60 硬上限。

**明确不做（记入最终 audit）**：四.1 第一轮盲评独立性（审阅自认需实验验证）；三.1 动态深读调度（轻量版仅升级抽取问题）；四.4 两模式内核完全统一（共享构建块在 chat-mode 落地）。

## 修复项 ↔ 审阅条目映射

| 修复项 | 审阅条目 | 验收标准 |
|---|---|---|
| 1.1 审计三状态 | R1 | 第 9+ gap 标 NOT_AUDITED 不进入 survivors；web 失败/解析失败 → INSUFFICIENT_EVIDENCE；审计数==参与 gap 数 |
| 1.2 排序反转 | R2 | 混合 rank/null 池中带 rank 者优先深读 |
| 1.3 反馈跨周期 | R3 | cycle1 reviewer 唯一标记出现在 cycle2 proposer prompt |
| 1.4 STOP 协议 | R8 | "Do not STOP; CONTINUE" 不判停；YAML 失败→纠正重试→parse_degraded 标记 |
| 1.5 空候选 | R6 | `gaps: []`/`ideas: []` 合法结束并产出报告 |
| 1.6 收敛参数 | R9 | min=2；max_rounds=60 到达即停（硬上限） |
| 1.7 角色缓存 | R7a | moderator 失败重试时 proposer/skeptic 不重跑 |
| 1.8 深读逐篇恢复 | R7b | 已深读论文从文件恢复，不重复调用 |
| 2.1 审计重写 | D1 | prompt 无 98% 通用规则；三值结论 |
| 2.2 定向查重 | D2 | duplicate-check stage 产出 closest_works+differentiation 并进品味门 |
| 2.3 品味门重写 | D3 | 知识增量追问；KILL 需 kill_evidence_type；无自动硬杀 |
| 2.4 深读问题升级 | D4 | 抽取含验证条件/替代解释/来源位置 |
| 2.5 否决记录 | D5 | REJECTION_LOG.md 含 reopen_condition |
| 2.6 chat 内核 | R4+D6 | 研究块注入 prompt；open_issues 跨轮传递；next_action 驱动停止 |
| 2.7 stress-test | R5 | 完整候选 brief；skeptic=judge 跨模型 |
| 2.8 成本报告 | D8 | COST_REPORT.md 逐模型 usage；MCP 计次数 |
| 2.4 附带 | D7 | discover prompt 收敛双写（措辞级） |

执行顺序：批次 1（1.1-1.8 独立 commit）→ 批次 2（2.1-2.8）→ 批次 3（全量测试 + discover/chat-mode/debate 真实 E2E，如实记录）→ 批次 4（逐条审核产出 review-audit.md）。
