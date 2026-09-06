# Prompt Inventory — ARC（prompt 优化阶段的输入文档）

更新于三 D 改版（discover / develop / debate）之后。所有 prompt 统一收纳在 `prompts/latest/`
下，按模式分目录；`resolve_prompt_path(mode, name, lang)` 是唯一加载入口（语言变体优先，
无后缀文件兜底）。

## 目录结构与加载方式

```text
prompts/latest/
├─ debate/      # arc run（正式辩论）
│  ├─ proposer / skeptic / moderator（各 _en/_zh + 无后缀）   ← agents/*.py 加载
│  └─ problem_framer_{en,zh}.md                              ← state.frame_problem（占位符 {raw_idea}）
├─ develop/     # arc develop（原 chat-mode）
│  ├─ proposer / skeptic / moderator（各 _en/_zh + 无后缀）   ← 辩论三轮
│  ├─ reviewer.md / drift_monitor.md                          ← 外层评审 + 漂移监测（仅此模式使用）
│  └─ consensus_synthesizer_{en,zh}.md + consensus_task_{en,zh}.md  ← 收尾共识导出（{topic} 占位）
├─ discover/    # arc discover（文献勘探）
│  ├─ theme_framer / gap_miner / saturation_auditor / duplicate_checker /
│  │  idea_generator / taste_judge                            ← 六个 stage 角色（仅 en）
│  └─ deep_read_question.md                                   ← 深读抽取问题（{无占位符}，经 scholaranalysis 执行）
├─ refine/      # arc refine-topic
│  ├─ writer_{en,zh}.md + writer_task_{en,zh}.md              ← {topic}/{critique} 占位
│  └─ reviewer_{en,zh}.md + reviewer_task_{en,zh}.md          ← {refined} 占位
└─ pipeline/    # arc pipeline
   └─ auto_review_task.md                                     ← {threshold}/{rid}/{max_rounds}/{memo} 占位
```

## 仍留在代码里的模板（运行时结构，非角色 prompt）

- `develop_runner` 三个 user-prompt builder：收敛压力注入、[RESEARCH OBJECT]/[OPEN ISSUES] 块
- `pipeline_runner._llm_generate`：语言策略提示（think English / output Chinese）
- `agents/*.py` 各 run()：轮次上下文注入结构（[UNRESOLVED BLOCKERS] 等）
- discover 的检索 query 模板（审计/查重的搜索词构造）
- MCP 服务端 prompt（ScholarAnalysis/ScholarTrace 内部）：ARC 无法直接优化，只能通过
  deep_read_question 这类问题文本间接影响

## Skills（第二 prompt 来源：SKILL.md 正文直接作为 system prompt）

- **develop** 加载 8 个：research-lit、idea-creator、novelty-check、evidence-grounding、
  research-refine、experiment-bridge、auto-review-loop、memo-synthesis
- **pipeline** 加载同样 8 个 + `pipeline-arc`（只用其 Stage Chain 段，正文不进 prompt）
  + debate-runner 阶段转调 debate 提示词
- skills 正文目前**只有产物名契约**（test_repo_contracts），质量零测试覆盖——prompt 优化的最大空白区

## 契约测试覆盖（test_prompts.py）

| 层 | 覆盖 |
|---|---|
| debate/develop 角色 + discover 六角色 | ✅ marker 全覆盖 |
| problem_framer / consensus / refine / pipeline 新提取文件 | ✅（本次补齐 marker） |
| skills 正文 | ❌（仅产物名） |
| 运行时注入模板 | ❌（按设计归运行时所有） |

## 参考项目映射（哪些设计参考了谁）

| 来源 | 借鉴点 | 落点 |
|---|---|---|
| ARIS（references/ARIS） | 轻量 skill 组织、可恢复循环 | skills/ 结构、run_state 恢复 |
| EvoScientist（references/EvoScientist） | 记忆与多阶段理念 | pipeline 多阶段 |
| Stanford AI-Researcher（references/AI-Researcher） | 围绕 idea 定向重检索再逐篇比较 | discover/duplicate_checker |
| Sakana AI Scientist（references/AI-Scientist） | 分阶段端到端流程 | pipeline stage chain |
| Google Co-Scientist（references/Co-Scientist，非官方复刻） | 多假设生成-锦标赛-演进 | 争点表（claim 版本化、可重开） |
| PaperQA2（references/paper-qa） | 检索/证据/引用分层 | 审计 INSUFFICIENT_EVIDENCE |
| Google Co-Scientist | 多假设保留、改进产生新候选 | 争点表（claim 版本化、可重开） |
| PaperQA2 | 缺证据 vs 证据矛盾的区分 | 审计 INSUFFICIENT_EVIDENCE 状态 |

## 优化优先级建议

1. **零覆盖区**：8 个 skill 正文 + 运行时注入模板（每轮真实消耗 token 但从未被审视）
2. **高杠杆单体**：`discover/gap_miner.md`（E2E 显示只挖 1 个 gap，偏保守）、
   `develop/moderator_en.md`（新控制契约需真实样本迭代）
3. **语言缺口**：discover 六角色 + deep_read_question 仅 en；reviewer/drift_monitor 仅 en
4. **护栏**：`arc prompts optimize` 必须把 test_prompts.py 的 marker 当不可变区；
   机器可读字段（YAML 键、[JUDGE_DECISION]、占位符名）变更需同步 parser 与测试
