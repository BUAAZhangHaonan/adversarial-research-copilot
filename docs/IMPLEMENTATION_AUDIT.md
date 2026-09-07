# ARC vNext 实现审计

<!-- ARC_CURRENT_DELIVERY_SUMMARY:BEGIN -->
## 当前交付摘要

本节来自最终保存文件；下方带日期、提交或历史停点的记录保留原样。当前结果优先查看 [交付说明](DELIVERY.md)、[最终状态快照](VALIDATION_SNAPSHOT.json)、[费用报告](COST_REPORT.md) 和 [同材料对照](L4_REPORT.md)。

- 已测代码提交：`a14da30f31a1541b9a5732c6aa3b85ab9dc689f9`；342 项测试通过，用时 65.59 秒。独立包验证记录：`work/release-verification.json`。
- 费用快照时间：`2026-09-07T10:36:14.234815+00:00`；父账户 `arc-vnext-validation-20260907`，限额 100.000000 元，已结算估计 45.154048–45.303543 元，预留 0.000000 元，未知调用 0，剩余 54.696457 元。不是供应商发票。

- [x] F 当前工程交付：已测提交、测试与包验证记录、wheel/sdist、要求的交付文档和静止账本快照已落地。
- L2：下表只统计真实入口执行完成记录。它不单独证明全部入口及争点补证验收通过；还需在交付说明/E2E记录中核对新增动作对应的 issue、证据与判断变化。
- L3：本摘要不从 MAIN_REPORT、单阶段 COMPLETED 或人工输入完成推断自然同卡贯穿。完整卡版本链和最终结果以交付说明为准；协议失败不是科学否决。
- L4：本摘要不从候选生成或 schema 接受推断质量对照通过。同材料双方、留出、匿名评价及未完成项以同材料对照报告为准；自动评价不是专家认可。

| 入口 | 保存的 COMPLETED 数 | 所有保存状态计数 |
|---|---:|---|
| discover | 1 | COMPLETED: 1, PAUSED_PROTOCOL: 3 |
| develop | 0 | PAUSED_PROTOCOL: 3 |
| run | 0 | PAUSED_PROTOCOL: 3 |

这些计数只反映最终快照，不能把不同人工输入拼成同一张自然卡。历史已接受对象、失败响应与工程测试均不改写。

| 摘要输入 | SHA256 |
|---|---|
| `docs/VALIDATION_SNAPSHOT.json` | `b34e9e1bc9fde974183748cddaf51fa6da3b39248e94bd23e256303ea75cd8b1` |
| `work/release-verification.json` | `661e2c7746652f3a87341b60b9cf1947f641582bcc2505fdb5b714c7812d35b4` |
| `docs/DELIVERY.md` | `a941381e6a72a855af6bb540de29c8fe6fa33798163ebfe19db1b56f80ed8a23` |
| `work/final-cost-summary.json` | `3c96c83eea46881bff5def4ee85acbae0ae111d9fb5761fd5b0b976d4fa0a494` |
<!-- ARC_CURRENT_DELIVERY_SUMMARY:END -->

记录边界：本页工程证据及运行状态保留为 `d0d7459` 文档时点的历史记录，截止三笔预算追加之前；“暂停”“运行中”和未勾选项均指该时点，不代表最终续跑结果。最新执行状态与费用以 `docs/VALIDATION_SNAPSHOT.json`、`docs/COST_REPORT.md`、`docs/L4_REPORT.md` 及最终续跑记录为准；相应最终材料未落地前不预填结果。三笔追加授权见 [BUDGET_EXTENSION_AUTHORIZATION.md](BUDGET_EXTENSION_AUTHORIZATION.md)。

验收契约：`EXECUTION_SPEC.md`，含附录 A–D。用户目标是得到有依据、有增量、可检验的研究卡及可行性分析；实验实施与论文由人完成。

## 版本与隔离

基线为 `3bc93dd0be54d3c2ffc4c2b4f9f2014c79064c85`（g203 原 master 干净）。修改位于 `codex/arc-vnext-20260907` 的隔离 worktree `/home/g203/zhanghaonan/arc-vnext-20260907`。原仓库、references、密钥、历史产物和三项 MCP 服务保持原状。提交 ID 见 git log；不推送、不合并。

采用 Typer/Pydantic、OpenAI SDK、官方 MCP SDK 2.x、Jinja StrictUndefined、SQLite 和文件。移除旧自制通信协议、关键词/分数控制、重复 reviewer 循环和旧 pipeline/chat-mode。删除清单为 `docs/REMOVED_TRACKED_FILES.json`，仅含受控旧实现；迁移见 `MIGRATION.md`。

d0d7459历史文档对应的代码验证基准为 `bac3659512f2bae137b8a0241b71c64c17ff3549`（机械搜索来源、重复命中、报告继承与实际查证契约修复）：326 tests passed / 66.28s，日志 `work/tests-contract-closeout.log`；该提交git archive构建的独立wheel/sdist及 `/tmp` 安装资源/CLI验证通过。历史5e3830c为290项/54.28s及独立安装通过；535357d为283项/52.08s，日志work/tests-claim-source.log。Windows此前282项/427.42s是更早快照；0f66f56的263项/48.55s、2b8b79a的258项/46.23s和eda3965的255项/47.29s均保留为历史验证，不将文档提交当作已测代码版本。

## d0d7459追加预算前的真实验收停点

Flash/Pro均已完成JSON、native tools、thinking/max、384000输出上限和stream的联合真实探针。每模型两次模型请求、一次实际read_record、repair_count=0，最终finish_reason=stop，均为COMPLETED。它们共用原100元父账户；实际请求ID、工具ID、费用及原件指针见 [JSON_TOOL_PROTOCOL](JSON_TOOL_PROTOCOL.md) 与 [E2E_REPORT](E2E_REPORT.md)。该读取是run元数据，不能代替影响科研争点的新证据。

L2显式软件输入develop在该历史快照中为 `PAUSED_BUDGET`：已花人民币4.106986–4.107017，剩余15.892983，低于下一次Pro请求所需15.912预留；round 1 moderator尚未完成。这是新请求准入暂停，没有截断已开始的回答，也不是科研否决。旧独立run因metadata-only空读循环由开发者在下一次准入处暂停，最终为PAUSED_PROTOCOL；临时单run INSERT gate已移除，未改预算或截断已开始请求。它不是生产自动循环检测。上述明确标记的输入不属于自然发现卡。Rendering自然run的shared_investigation已在bac3659下零新增调用恢复为ACCEPTED并登记19条findings，随后自然卡v1已保存，draw1.novelty在PENDING时因阶段预留不足暂停，selector未执行；追加授权前的停点见下文。

V3自然卡已保存，但novelty在一次结构修复后仍为 `INVALID_OUTPUT_AFTER_REPAIR`，没有accepted novelty。L2三入口尚未全部完成，L3自然同卡未完成；L4同材料对照已按计划启动，尚无结果。已有工程测试和联合探针不能关闭这些验收项。

## 十八项决定逐条对应

| 决定 | 代码/资源与验收证据 |
|---|---|
| 科研品味 | research_policy/selection_examples/selector；validation.validate_selection 对推荐先决条件及组合例外作结构校验；test_selection 六类例子。科学语义仍待人审。 |
| 研究卡深度 | schemas.CardDraft：锚点、增量、动机、最近工作、竞争解释、最小检验、资源、风险和主张；缺字段拒绝。 |
| 主报告/待补证 | SelectorResult 与独立 selection_checks；未实验本身不导致待补证。报告另分技术未完成。 |
| 资源 | resource_policy + ResourceEstimate：3090 24GB/A100 假设、数量、训练/推理 GPU-hours、wall time、工作量/依据/不确定性；没有实际启动科研实验。 |
| 五次抽卡 | Campaign 原子 claim_draw；每次一个核心卡，共享调查；档案语义比较及重开证据，空卡也消耗已开始机会，预算前置。 |
| develop 权限 | 冻结原锚点，新增版本；validate_revision 校验受影响 claim；原卡不可覆盖；转向先原文复核后单事件冻结。 |
| 自动衔接 | CLI 三主命令分别停止；test-e2e 必须显式 --allow-stage-transition，常规默认关闭。 |
| 定向补证 | WorkflowEngine 的 evidence requests/RETRIEVE + 唯一 SDK tool loop；新颖性和 develop 必须有成功外部动作 trace。 |
| 来源层级 | SourceRecord/EvidenceRecord：原文、metadata、secondary_analysis；工具返回全文另存，摘录/位置与原文校验，来源 ID 由 registry 管理。 |
| 模型 | config.roles 仅 Flash/Pro，第一版全部 max；实际请求使用 thinking enabled、reasoning_effort max、384000 输出上限。 |
| 20 元预算 | discover/develop/run 每个用户阶段一个预算账户，全部角色/重试/MCP 纳入；发起前保守预留，不动态缩短已开始回答。 |
| 记忆 | SQLite/中文 bigram FTS5 BM25 召回，稳定 ID 精查和有限窗口/分页，librarian 判断实质关系；保存重开条件，无用户品味学习。 |
| 只改 ARC | MCP 映射是 ARC 适配配置；成本不明的能力记录需求，不修改外部服务。 |
| 清理兼容 | 废弃接口和旧状态不做兼容；保留旧产物，导入新卡需显式动作。 |
| 中文报告 | 确定性 Markdown 模板：短总览、逐卡详情、当前争点、原文定位、费用和停止原因；不可把 completed 当 idea 通过。 |
| 分层验收 | L1 工程、L2 真实入口、L3 自然同卡、L4 同材料对照分别报告；见 E2E_REPORT，不以测试数量替代真实验证。 |
| 环境 | g203 隔离 venv 与 wheel 安装；锁文件固定经过验证的依赖；仓库外调用已检查。 |
| 100 元调试总额 | `.arc-validation/arc.sqlite` 固定父账户 `arc-vnext-validation-20260907`；所有探针、E2E、失败、修复后验证及对照共用；见 COST_REPORT。 |

## 契约章节与附录

- §2：官方模型/价格、SDK 和六参考项目取舍见 SERVICE_AUDIT、BASELINE_AUDIT；参考代码只读，不纳入运行时扫描。
- §3：schemas/store 管统一对象、事务和不可变原件。Markdown 是视图，SQLite 是状态权威。
- §4：workflows 的 discover/develop/debate 三入口共用 call/investigate/issue kernel，不调用科研实验或论文工具。
- §5：typed selector + 跨记录校验与六类语义例子；结构校验不能证明模型判断正确。
- §6：按主题/卡召回有限档案；下一阶段从源 ID 读取原调查；候选不继承旧的通过结论。
- §7：整数微元账本、祖先准入、价格快照、逐请求 usage/原始响应、保留未知预留、任务/工具断点和 prompt 冻结。
- §8：27 个附录原稿 Markdown 均落地；manifest 登记装配、工具 schema 来自实际接口、动态材料只作数据。新增导入和恢复所需资源及小幅协议澄清均在 PROMPT_INVENTORY 列明。
- §9：角色可配置，当前默认分工与契约一致；reporter 使用确定性模板时无需额外付费模型调用。
- §10：B01–B18 对应下表。
- §11：先冻结 EVAL_PLAN 后真实调用；预算、错误输出和未完成验证保留。
- §12：README/CLI help 提供三个命令、status/resume、显式追加预算和转向重开。
- 附录 A：完整资源与 hash 校验，见 PROMPT_INVENTORY/test_prompts。
- 附录 B：统一 Envelope[T] 和13种结果 schema；IMPORT/SCOPE_AUDIT 等额外登记任务复用所属角色的结果类型。B3 资源/费用必需字段、B4 manifest、B5 task/call/trace 可观察性均有持久化对象；B6 层级如实分开。
- 附录 C：文档已提供来源；可变的接口参数、人民币价格和 MCP SDK 用当前官方资料及真实请求复核，不把社区修复声明当验收。
- 附录 D：上述十八项映射与下面 B01–B18，以及 E2E/COST 报告共同提供证据，不另行宣称全部真实场景已通过。

## B01–B18 审阅问题

以下状态指替换实现及回归覆盖，不声称已在旧基线逐一复现。旧版87项测试通过仅是基线记录。测试名称已经对本地 `work/arc-vnext/tests/` 函数定义核对；replaced 不等于真实 L2/L3/L4 已通过。本文件矩阵和d0d7459历史状态是该次交付核对依据，未纳入受控交付的旧核对草稿不作为最新验收记录。

| ID | 状态 | 替换实现与具体测试 |
|---|---|---|
| B01 | replaced | mcp_client 官方 SDK+deadline；test_silent_partial_line_and_eof_stdio_terminate、test_sse_missing_endpoint_and_early_eof_exit。 |
| B02 | replaced | debate 轮前上限、单一 process_ruling、接受轮后动作恢复；test_round_limit_and_resume_cover_each_control_branch（STOP/REASON/RETRIEVE）及 test_resuming_at_round_limit_makes_no_new_call。 |
| B03 | replaced | Runtime 每次完整 Envelope 原子 accepted，无旧 scorecard；test_single_structural_repair_and_original_failure_preserved。 |
| B04 | replaced | 无正文关键词停机/默认分数；tests/test_contracts.py 的 test_moderator_plain_stop_and_score_are_not_control_contract 明确拒绝正文 STOP/score 对象；tests/test_runtime.py 的 test_nonempty_invalid_finish_never_accepted_or_repaired 拒绝截断等不合格响应。 |
| B05 | replaced | 冻结 campaign 主题，无固定多模态 fallback；test_five_failed_draws_share_investigation_and_never_fake_a_card、test_user_question_import_does_not_create_campaign_or_change_topic。 |
| B06 | replaced | 实质覆盖必须原文依据及具体工作/条件；test_selection 的 covered/unverified/source mismatch 反例；检索失败属执行限制。 |
| B07 | replaced | registry/任务对象持久化；test_source_access_and_provenance_survive_recovery、test_successful_tool_reused_after_next_request_budget_pause。 |
| B08 | replaced | extra forbid、ID/集合/引用严格；tests/test_contracts.py 的 test_all_thirteen_registered_semantic_contracts_are_closed、test_duplicate_claim_ids_and_non_object_candidates_are_protocol_errors；tests/test_runtime.py 的 test_semantic_hallucination_not_repaired_into_success；tests/test_evaluation.py 的 test_evaluator_cannot_omit_candidate_judgments_and_report_completion。 |
| B09 | replaced | src/arc/config.py 的 Settings 约束 draws/max_rounds；旧 deep_read 成功数量门槛和按可空论文分数排序已删除。src/arc/store.py 的 lookup_archive 采用 BM25 与 stable ID 排序；tests/test_cli.py 的 test_unknown_model_and_nonmax_effort_rejected、tests/test_store.py 的 test_same_chinese_title_does_not_collide_and_archive_is_paginated 是现有相关测试。没有单独“nullable metadata 排序”回归，不将其列为已测。 |
| B10 | replaced | ID/version 路径；test_report_rejects_path_derived_from_title_or_untrusted_id、test_card_versions_are_immutable_and_idempotent_across_crash。 |
| B11 | replaced | budget_calls 包含全部尝试/祖先账户/未知费用；test_parent_includes_all_child_stages_and_own_calls、test_unknown_attempt_preserves_reservation_and_retry_is_separate、test_tariff_boundary_and_reasoning_is_not_double_billed。 |
| B12 | replaced | context 使用完整锚点/claim/证据/ledger；tests/test_workflows.py 的 test_three_stages_keep_same_card_and_full_anchor_without_auto_transition、test_resume_reuses_proposer_skeptic_and_long_context_tail；tests/test_store.py 的 test_full_original_preserves_decisive_condition_at_long_document_end；tests/test_runtime.py 的 test_service_adapter_registers_original_without_truncating_paper。 |
| B13 | replaced | 新版本与目标 claim/version 证据重验；test_claim_version_cannot_regress_or_reclassify_without_new_version、test_targeted_finding_resolves_existing_second_version_claim。 |
| B14 | replaced | 前版完整 issue ledger +逐项转移、事件幂等；test_issue_ledger_preserves_unseen_issues_and_validates_transitions、test_issue_event_replay_and_round_checkpoint_are_one_transaction。 |
| B15 | replaced | execution/assessment 分离，跨记录无效推荐暂停且不重复付费；test_cross_record_invalid_selection_pauses_without_acceptance_or_paid_replay、test_later_stage_reports_final_assessment_instead_of_old_selection。 |
| B16 | replaced | 明确 CLI 覆盖优先级，移除别名兼容；test_explicit_cli_options_override_config_without_default_shadowing。 |
| B17 | replaced | SDK 实际请求、流终止、usage、reasoning tool 回传；test_actual_sdk_request_max_full_output_usage_and_role_resume、test_native_tool_reasoning_association_and_trace；真实两模型 trace 见 E2E_REPORT。 |
| B18 | replaced | 真 trace 条件与定向补证链引用；test_actual_searches_must_cover_successful_search_trace、test_novelty_requested_evidence_trace_is_kept_through_continuation；实际搜索零结果与有覆盖的非空正文读取分别检查，tests/test_evidence_gates.py 的 test_empty_external_reads_do_not_satisfy_verification_or_replay、test_successful_zero_result_search_counts_as_search_not_original_read；真实工具范围及外部限制见 E2E_REPORT。 |

## 全文交付映射与状态含义

本轮只核对限定交付文档与当前源码/测试，不重新运行付费任务。`confirmed_fixed` 指已观察到的缺陷有修复及对应验证；`already_fixed` 只用于无需本轮修改且已有直接通过证据的要求；`replaced` 指旧结构已被新契约替换，不能反推旧BUG已复现；`not_reproduced` 指实际尝试仍不能重现，不代表无缺陷；`blocked` 指关闭验收所需证据仍缺，未必表示运行进程阻塞。不为凑齐标签而声称做过旧版本重现。下表静态结论均不能代替动态验收。

| 契约范围 | 状态及可核对依据 |
|---|---|
| §0、§1.1–1.2 身份、18项决定与歧义 | replaced：前述18行逐项映射；`docs/BASELINE_AUDIT.md`、`docs/REMOVED_TRACKED_FILES.json`、`.gitignore`、`docs/MIGRATION.md`记录隔离与删除范围；`tests/test_cli.py` 的 test_stage_transition_not_authorized_by_default、test_removed_entry_points_do_not_start_work 验证新入口。研究实验/写论文不属于注册工具。 |
| §2.1–2.3 公开依据 | already_fixed（资料与范围记录）：`docs/SERVICE_AUDIT.md`、`docs/reference-review-notes.md`、`configs/pricing.json`；真实参数/usage证据在E2E_REPORT，价格不是余额接口推得。参考效果不外推为ARC质量。 |
| §3.1–3.4 状态/卡/证据关系 | replaced：`src/arc/schemas.py`、`store.py`；`tests/test_contracts.py` 的 test_card_cannot_silently_drop_required_research_material、test_resource_units_and_gpu_assumptions_are_explicit；`tests/test_store.py` 的 test_card_versions_are_immutable_and_idempotent_across_crash。卡信息包含竞争解释、最小检验、条件/单位和资源依据。 |
| §4.1–4.4 三入口/单一控制 | replaced（工程）：`src/arc/workflows.py`、`validation.py`、`cli.py`；下方§11抽卡、继承和恢复行。自然同卡真实链尚为blocked（验收未齐）。 |
| §5.1–5.4 六类判断边界 | replaced（契约）：`prompts/common/selection_examples.md`、`src/arc/validation.py`及 `tests/test_selection.py`；同问题新知识不等于重复，尚未实验不等于无依据。真实误判率及组合例外是否可信仍为blocked（未完成L4/人审）。 |
| §6 文献/档案/能力 | replaced：`src/arc/mcp_client.py`、`runtime.py`、`store.py`；`tests/test_mcp.py` 的 test_unobservable_cost_blocks_before_session 与§11上下文/证据行。收费服务无可靠费用上界时保留能力需求，见 `docs/MCP_REQUIREMENTS.md`。 |
| §7.1–7.4 账本/准入/尝试/恢复 | replaced：`src/arc/budget.py`、`pricing.py`、`runtime.py`；B11、§11预算/回复/恢复行。`tests/test_budget.py` 的 test_call_ledger_preserves_full_usage_and_does_not_invent_actual_invoice 区分估计、usage与发票；未知费用不清零。 |
| §8.1–8.3 Markdown/装配/JSON | replaced：`src/arc/prompting.py`、`runtime.py`、`prompts/manifest.json`；附录A/B逐项映射如下。 |
| §9 默认角色 | already_fixed（当前配置核对）：`src/arc/config.py`、`configs/runtime.yaml`；Flash为investigator/librarian/discovery/developer/proposer，Pro为novelty_examiner/selector/skeptic/moderator/evaluator；reporter配置为Flash但实际报告直接渲染。`tests/test_cli.py` 的 test_unknown_model_and_nonmax_effort_rejected 与B17确认只许Flash/Pro及max；没有角色自动降级。 |
| §10 旧BUG | replaced：前述B01–B18表，不假装逐一旧版复现。后来真实暴露的原文/版本/恢复缺陷在后文按confirmed_fixed另记。 |
| §11 批次A–C | replaced：基础契约与三入口已接通；`src/arc/bootstrap.py` 的progress和 `runtime.py` 的_progress在请求准入/结算时输出预算、task、draw、轮次、run状态；`cli.execute`结束时输出stop_reason。它是事件进度，不是token级流式显示。 |
| §11 批次D–E与最终交付 | D的替换工程覆盖见下表；E为blocked（真实结果未齐）：冻结计划见 `docs/EVAL_PLAN.md`，真实执行见E2E_REPORT，最终成本仍须由原父账本汇总。测试通过不关闭E。 |
| §12 CLI | replaced：`src/arc/cli.py` 的discover/develop/run/status/resume/restart-direction/test-e2e/test-compare；`tests/test_cli.py` 的 test_explicit_cli_options_override_config_without_default_shadowing、test_user_question_import_does_not_create_campaign_or_change_topic。旧stress-test别名是可选项，已移除，不作为缺项；新方向用restart-direction显式开新campaign。 |

## §11 离线矩阵逐行核对

以下既有回归及新增契约反例均包含在 `bac3659` 的326项整合测试中。实现与测试的文件名均为仓库相对路径；不把模拟模型的答案当成真实科研证据。

| 矩阵行 | 状态 / 文件与回归证据 | 未被该测试证明的部分 |
|---|---|---|
| 抽卡 | replaced；`tests/test_workflows.py`：test_five_failed_draws_share_investigation_and_never_fake_a_card、test_one_good_card_then_no_distinct_direction_stops_before_five、test_same_contribution_cannot_fill_multiple_draws_by_rewording、test_failure_before_draw_admission_does_not_spend_draw_or_repeat_shared_work；`tests/test_store.py`：test_draw_claims_are_atomic_idempotent_and_never_reset；`tests/test_selection.py`：test_previously_asked_question_is_not_covered_contribution。 | 模型在真实主题中会否产生实质不同的好问题。 |
| 提案继承 | replaced；`tests/test_cli.py`：test_card_stage_inherits_scoped_original_material_without_prior_approval；`tests/test_workflows.py`：test_three_stages_keep_same_card_and_full_anchor_without_auto_transition、test_develop_requires_real_trace_not_claimed_fresh_verification、test_scope_change_audits_original_freezes_once_and_does_not_develop_branch。 | 真实develop/run及改变具体争点的新trace未全部完成。 |
| 判断边界 | replaced；`tests/test_selection.py` 六类测试及 test_required_knowledge_gates_cannot_be_marked_not_applicable、test_not_applicable_is_allowed_only_for_stitching_check；`tests/test_contracts.py`：test_reasonable_unperformed_experiment_can_be_promising_handoff。 | 合成例验证门槛，不验证实际科学判断正确。 |
| 预算 | replaced；`tests/test_budget.py`：test_five_draws_share_one_stage_budget_and_resume、test_parent_includes_all_child_stages_and_own_calls、test_unknown_attempt_preserves_reservation_and_retry_is_separate；`tests/test_pricing.py`：test_tariff_boundary_and_reasoning_is_not_double_billed、test_missing_cache_and_usage_keep_conservative_upper；`tests/test_mcp.py`：test_unobservable_cost_blocks_before_session。 | 已知服务上界不能冒称正式逐请求发票。 |
| 完成当前回复 | replaced；`tests/test_runtime.py`：test_budget_admission_precedes_draw_callback_and_no_dynamic_shortening、test_nonempty_invalid_finish_never_accepted_or_repaired；`tests/test_pricing.py`：test_full_context_joint_upper_covers_both_long_input_and_long_output。 | 不故意烧光20元制造真实边界；完整读取在mock精确测。 |
| 恢复 | replaced（离线）；`tests/test_workflows.py`：test_resume_reuses_proposer_skeptic_and_long_context_tail；`tests/test_runtime.py`：test_successful_tool_reused_after_next_request_budget_pause、test_response_saved_before_validation_recovers_locally_after_long_pause、test_corrupt_snapshot_refuses_resume_without_new_model_request；`tests/test_prompts.py`：test_resumed_repair_uses_frozen_markdown_not_live_templates。 | confirmed_fixed：work/ssh-detached-verification.json证明启动SSH正常退出后独立进程继续完成真实响应/repair并开始下一任务。工程恢复已覆盖旧日期、保存响应和重建runtime，不含实际等待24小时；后者不是新增验收阻塞。强制断网及provider断流恢复未实测，作为证据范围保留。 |
| 证据 | confirmed_fixed / replaced；`tests/test_mcp.py`：test_strict_arguments_and_untrusted_urls；`tests/test_store.py`：test_missing_or_invented_source_and_excerpt_are_rejected、test_secondary_analysis_cannot_be_marked_original_or_verified、test_source_mirrors_share_canonical_identity_not_independent_evidence、test_same_named_claims_on_different_cards_cannot_transfer_target_evidence；`tests/test_selection.py`：test_covered_work_cannot_borrow_verified_evidence_from_another_source。 | exact摘录不证明复合主张成立，见V3_EVIDENCE_REVIEW。 |
| 上下文 | replaced；`tests/test_workflows.py`：test_context_contains_only_relevant_evidence_not_entire_archive、test_resume_reuses_proposer_skeptic_and_long_context_tail；`tests/test_store.py`：test_full_original_preserves_decisive_condition_at_long_document_end、test_same_chinese_title_does_not_collide_and_archive_is_paginated；`tests/test_runtime.py`：test_native_tool_reasoning_association_and_trace、test_service_adapter_registers_original_without_truncating_paper。 | 没有量化声称中文召回率或实际token节省。 |
| 提示词 | replaced；`tests/test_prompts.py`：test_unregistered_or_missing_resources_fail_before_invocation、test_duplicate_manifest_and_undefined_variables_fail、test_data_is_never_a_template_and_repair_retains_semantic_contract、test_ast_checks_dict_tool_descriptions_and_raw_messages；`tests/test_runtime.py`：test_repair_cannot_invent_reference。 | AST只扫描生产ARC，不扫描第三方references。 |
| 安全与隔离 | replaced（权限边界）；`tests/test_mcp.py`：test_strict_arguments_and_untrusted_urls；`tests/test_cli.py`：test_stage_transition_not_authorized_by_default；`tests/test_prompts.py`：test_data_is_never_a_template_and_repair_retains_semantic_contract。`src/arc/runtime.py` 的工具集合不提供shell/预算修改/科研执行接口，外部内容不写Settings。 | 这是代码权限与注入数据边界，不是通用模型抗提示词攻击率测评；未修改第三方仓库由隔离/变更清单核对。 |

## 附录 A–D 的独立核对

附录A为already_fixed（原稿落地），共27份，而不是27个语义调用。`tests/test_prompts.py::test_spec_assets_are_exact` 从任务书独立提取并逐文件比较。该代码快照中23份全文相等，developer/investigator/output_protocol/read_record四份保留完整原稿前缀后追加；本轮独立比较也检查这个边界。output_protocol归属说明随2b8b79a追加，read_record的Cached source coverage与metadata-only说明随535357d提交，均包含在该快照326项测试中。本次source_recheck删除内联句子，不修改任何Markdown/schema，仍为23份全文相等与4份完整前缀。追加理由见PROMPT_INVENTORY/PROMPT_CALIBRATION/CLAIM_AND_SOURCE_FIXES；不把四份追加文件称为全文仍与附录相等。

| 附录编号 | 仓库内文件 |
|---|---|
| A1–A5 | `prompts/common/research_policy.md`、`evidence_policy.md`、`output_protocol.md`、`selection_examples.md`、`resource_policy.md` |
| A6–A10 | `prompts/roles/investigator.md`、`librarian.md`、`discovery.md`、`novelty_examiner.md`、`selector.md` |
| A11–A16 | `prompts/roles/developer.md`、`proposer.md`、`skeptic.md`、`moderator.md`、`reporter.md`、`evaluator.md` |
| A17–A18 | `prompts/tasks/invoke.md`、`repair_structure.md` |
| A19–A25 | `prompts/tools/search_literature.md`、`read_paper.md`、`search_web.md`、`read_web.md`、`lookup_archive.md`、`read_record.md`、`request_capability.md` |
| A26–A27 | `prompts/reports/overview.md`、`card.md` |

| 附录B条目 | 状态及文件/测试证据 |
|---|---|
| B1 信封与请求 | replaced：`src/arc/schemas.py` 的Envelope/EvidenceRequest；`tests/test_contracts.py` 的 test_complete_envelope_cannot_omit_payload_or_invent_execution_control、test_needs_evidence_must_be_actionable；`tests/test_workflows.py` 的 test_needs_evidence_executes_targeted_check_then_revisits_exact_selection。前置请求绑定真实run/task，非空目标必须在冻结输入中可见。 |
| B2 13种结果、issue/control | replaced：`tests/test_contracts.py` 的 test_all_thirteen_registered_semantic_contracts_are_closed；`tests/test_store.py` 的 test_issue_ledger_preserves_unseen_issues_and_validates_transitions、test_empirical_issue_cannot_be_reclassified_to_bypass_evidence。registered IMPORT/SCOPE_AUDIT复用角色schema，reporter不实际付费调用。 |
| B3 卡/资源/费用字段 | replaced：`src/arc/schemas.py`、`budget.py`；`tests/test_contracts.py` 的 test_resource_ranges_reject_invalid_bounds、test_resource_units_and_gpu_assumptions_are_explicit；`tests/test_budget.py` 的 test_call_ledger_preserves_full_usage_and_does_not_invent_actual_invoice。 |
| B4 装配与工具子集 | replaced：`prompts/manifest.json`、`src/arc/prompting.py`；`tests/test_prompts.py` 的 test_registered_roles_render_traceable_task_and_minimal_prefix、test_resumed_repair_uses_frozen_markdown_not_live_templates。报告走确定性模板，同材料评价不在线扩展。 |
| B5 可观察性/AST/报告 | confirmed_fixed / replaced：`src/arc/reports.py`、`runtime.py`、`.gitignore`；`tests/test_reports.py` 的 test_report_links_actual_local_original_and_prompt_artifact、test_deterministic_report_rebuild_and_empty_discovery、test_cross_run_report_resolves_only_referenced_inherited_evidence；完整prompt/输入/环境快照测试见下方验证解释。原始reasoning本地恢复，不进入对外研究报告。 |
| B6 分层验收 | already_fixed（计划/层级边界）：`docs/EVAL_PLAN.md`、`src/arc/evaluation.py`；`tests/test_evaluation.py` 的 test_same_card_final_scientific_assessment_does_not_erase_l3_completion、test_develop_rejection_does_not_force_pressure_test、test_frozen_needs_evidence_is_saved_without_online_expansion_or_repeated_call。blocked（真实完成证据）：L2/L3/L4仍未齐，不能由这些测试勾选。 |

附录C为already_fixed（来源清单与适用范围）：S01–S10官方接口/SDK/Jinja、P01–P05论文与官方研究说明、C01–C05社区观察、R01–R07用户基线与六参考快照均在任务书可定位。`docs/SERVICE_AUDIT.md` 和 `docs/reference-review-notes.md`记录实际采用范围。ARIS、Stanford AI-Researcher、Sakana AI-Scientist、PaperQA、EvoScientist、Kaimen Co-Scientist均已覆盖；Kaimen是非Google官方复刻。未将一般论文问答/辩论表现当ARC质量依据，本轮文档核对也不是再次联网验证所有链接。

| 附录D编号 | 状态 / 直接对应证据 |
|---|---|
| D1 三入口/分段 | replaced（CLI与§11继承行）；blocked（L2三入口真实结果未齐）。 |
| D2 五次/差异/共同预算 | replaced（§11抽卡/预算行）；真实差异质量尚不由fixture保证。 |
| D3 继承/新增定向证据/版本 | confirmed_fixed / replaced（B12/B13、§11继承行）；blocked（真实同卡跨阶段链未齐）。 |
| D4 未实验可主推/不可辨识分流 | replaced（§11判断边界行）；真实科研价值仍待材料复核。 |
| D5 拼接例外 | replaced（test_combination_exception_needs_both_gain_and_interaction）；该测试不把口头效果承诺变成科学依据。 |
| D6 全部Markdown | already_fixed（附录A、B4/B5、生产AST）；完整来源hash/安装资源验证如下。 |
| D7 两模型真实max | confirmed_fixed（B17及E2E_REPORT两次真实probe）；没有比较不同思考强度优劣。 |
| D8 阶段/父预算/完整回复 | replaced（§11预算/回复行）；blocked（最终累计费用与外部未知费用的完整交付仍待记录）。 |
| D9 恢复不偷换成功 | confirmed_fixed / replaced（§11恢复/证据行、V2拒绝和V3独立recheck）；启动SSH正常退出后的独立进程存活已实测；实际>24h、强制断网/provider断流恢复仍未验证。 |
| D10 转向单事件 | replaced（test_scope_change_audits_original_freezes_once_and_does_not_develop_branch、test_scope_change_cannot_claim_original_revisit_without_read_trace）。 |
| D11 来源/成本/权限 | replaced（§11证据/安全行、B3/B5）；源可定位与科学论证成立分别报告。 |
| D12 中文报告/无假证明 | already_fixed（`tests/test_reports.py` 的 test_report_preserves_state_judgments_versions_and_costs、test_later_stage_reports_final_assessment_instead_of_old_selection）；blocked（真实最终卡/费用报告和L4人审尚未关闭）。 |

## 安装包的独立验证

该历史快照 `bac3659` 的受控git archive源码已分别构建wheel和sdist，并在独立 `.venv-wheel` 安装后从 `/tmp` 执行 `work/check_installed.py` 与 `arc --help`，CLI及prompt/报告/配置资源均通过。远端日志为 `work/wheel-build-bac3659.log`、`work/wheel-install-bac3659.log`、`work/wheel-help-bac3659.log`；它与326项整套测试对应同一代码提交。历史5e3830c和535357d的整套与独立安装结果分别为290项/54.28s、283项/52.08s，不能反向覆盖后续修复。

历史安装快照：`eda3965` 从受控git archive源码构建wheel及sdist，产物位于远端 `work/release-dist-eda3965/`，日志为 `work/wheel-build-eda3965.log`、`work/wheel-install-eda3965.log`、`work/wheel-help-eda3965.log`。在独立 `.venv-wheel` 安装后，从 `/tmp` 执行 `work/check_installed.py`，确认0.2.0版本、15个登记语义prompt及报告/配置资源可加载，OpenAI 2.54.0、MCP 2.1.1。该验证不依赖仓库cwd或pytest的pythonpath；结果由主线程实际运行记录，本轮没有再次安装或远端写入。

`pyproject.toml` 显式打包arc、arc_prompt_assets、arc_config_assets及Markdown/JSON/YAML；`tests/test_prompts.py::test_installed_package_loads_from_other_directory` 是另一个本地资源回归，不能单独替代上面的独立wheel验证。

## 验证解释

离线 fixture 是合成结构/控制反例，不是专家 gold label。已安装 wheel 从 `/tmp` 调用且包资源不依赖 cwd；各提交对应的测试和安装快照见 E2E_REPORT。真实同卡和对照的结果与付费账本独立记录，不以自动评价数量、KEEP 比例或模型自评分证明科研质量提高。

附录 B5 的完整输入/恢复检查有直接测试：tests/test_runtime.py 的 test_nested_existing_input_evidence_manifest_and_actual_dependency_snapshot、test_corrupt_snapshot_refuses_resume_without_new_model_request、test_changed_sdk_environment_requires_explicit_fork；tests/test_prompts.py 的 test_production_prompt_boundary 扫描 ARC AST，test_ast_boundary_rejects_illegal_calls_and_ignores_third_party 明确排除第三方目录。这些检查与单纯搜索提示词关键字不同。

§7.4取消任意“24小时后不可续跑”的失效规则，§11要求验证超过24h仍可恢复。对应工程测试使用旧日期和重建runtime：test_response_saved_survives_parse_failure_and_old_date、test_response_saved_before_validation_recovers_locally_after_long_pause。它们验证无任意失效及保存状态恢复，不声称实际等候24小时；任务书没有把额外等待24小时设为新的发布阻塞。独立的work/ssh-detached-verification.json现已记录启动SSH正常退出后，从新连接观察ARC继续完成响应并开始下一任务；该精确定义的SSH退出存活已实测，不扩大为强制断网或provider流式断流恢复。

IMPLEMENTATION_CHECKLIST 的 D1 勾选代表已提交版本的替换实现与离线工程检查，不能代替 §11 全部真实场景；E0、E1a、E1b分别记录计划、协议探针和三入口数据传递。具体测试版本、运行状态与费用以 E2E_REPORT 和最终账本报告为准，不用历史测试数量推断待提交修复的结果。

## 真实验证暴露的软件缺陷与修复

第一轮真实调查中，同一 arXiv HTML 的 7000 字符前缀加服务截断标记被误登记为完整原文，第二次67082字符完整读取因此触发来源冲突。原始两次 MCP 返回均已保存，没有把错误当无证据或科研否决。修复为：明确 representation、完整度和总长，只接受相同 representation 的严格前缀扩展；按 call_id 先保存原始工具结果，登记失败可在本地重解析，禁止重发成功工具。

回归还修复：跨记录非法推荐暂停而不接受；首次空档案召回也冻结，避免恢复时被本轮新卡污染；定向补证后保留真正的子任务 trace；新增 Finding 的成对目标 claim/version；已有 empirical issue 不可换种类绕过证据；claim 不可退版；转向复核必须是原文。协议字段扩展会使旧未完成 task 明确要求 fork，不静默替换旧 hash/提示词。

同材料对照另修复：manifest 首次冻结后不可覆盖，STOP 不继续 COMPOSE，needs_evidence 不触发在线补证，非法 selection 不入账，评价集合必须完整。自然同卡最终 REJECTED/NEEDS_EVIDENCE 是合法研究结果，不能误写成软件链路未完成；develop 已否决时仍不强行进入 run。同名验证 campaign 不接受不同 topic。

逐任务另保存嵌套输入的实际 evidence manifest、Python/SDK 依赖快照及 hash，报告追踪索引链接环境快照。恢复核完整 rendered prompt/修复 prompt 及消息前缀；依赖版本漂移明确要求 fork，不以旧结果伪装新版本成功。

正式 `develop/run --card` 还通过精确 card/version 关联继承原始调查材料和安全的调查任务指针；同主题别卡不混入，旧 assessment 不复制。对应 test_card_stage_inherits_scoped_original_material_without_prior_approval 及 Store provenance 隔离测试。

第三轮前，真实调查返回15条finding，其中13条摘录不符合已存原文；原因含跨段省略号拼接、改写引用、metadata snippet无正文，以及部分主张范围过度外推。原件和逐条核对见 [PROMPT_CALIBRATION.md](PROMPT_CALIBRATION.md) 与 [SOURCE_SPOTCHECK.md](SOURCE_SPOTCHECK.md)。没有把它们自动改写成可通过证据。

代码修复（a8ddc5a，confirmed_fixed）：Runtime在ACCEPTED前执行无副作用来源校验，历史accepted复用也需通过现有来源校验；Store先整批校验再事务写入；跨记录StateError明确PAUSED_PROTOCOL，不参与科学结论。测试 `test_bad_finding_quote_pauses_before_acceptance_without_semantic_repair`、`test_cached_invalid_finding_stays_protocol_paused_without_new_draw_or_paid_replay`、Store batch/source预检反例验证没有半批证据和新付费重试。旧V2经离线复查停为PAUSED_PROTOCOL，accepted/账本/原件不变，请求增加0。

同次修复让FRAME看到已登记seed材料，并将run.prompt_version改为整个已登记prompt bundle的hash，正文修改不再只隐藏于未变的manifest hash之下。对应 `test_discovery_frame_receives_seed_material_provenance_before_new_searches`、`test_new_run_prompt_version_changes_with_role_text_without_manifest_change`。原任务快照不改，新V3独立创建。提示词仅追加通用精确摘录与主张范围说明，留出未参与；是否改善由后续真实结果决定。

V2离线重验后的明确停点为 `PAUSED_PROTOCOL / excerpt_not_in_returned_source`。原accepted/raw均保留，离线操作新增请求0；当时父账本为141调用、人民币2.480237–2.480271。这是V2复核时点，不能代称包含后续V3的最新累计费用。

V3原最终回复不是JSON；仅一次格式修复后返回complete，但3个前置EvidenceRequests缺少claim/issue/draw归属。另一项原文检查显示17条引文中16条精确匹配，剩余一条将返回正文的 `20\(\times\)` 改成 `20x`，仍被拒绝。格式修复成功不等于科学结果或证据登记成功，也不能由该计数推断科研质量改善。

该轮受限复核修复已随 `acc012a` 提交：前置request通过上下文绑定，JSON Schema不变；excerpt mismatch允许恰好一次独立 `source_recheck`，同模型、同预算，仅开放 `read_record` / `request_capability`，不修改原失败任务、不降低来源要求。真实V3的source_recheck现为ACCEPTED，新增18条finding通过严格原文校验；原shared_investigation仍为PAUSED_PROTOCOL。Nature目标实际读取3次，call ID及只读审计路径见E2E_REPORT。

后续draw1.next通过，COMPOSE已ACCEPTED并生成 `clm_meas_01` 至 `clm_meas_07` 的version 1草稿；save_card却因 `claim_evidence_version_mismatch` 暂停。9处引用均是不同claim ID之间的背景依据，不是同ID旧版本证据偷渡。这是卡保存的工程停点，不是科研否决。原件、旧草稿和EvidenceRecord没有被手工改写。

历史修复 `eda3965` 区分两类关系：跨ID背景引用合法并在workflow/report公开binding，`verification_transferred`始终为false；同ID旧version仍拒绝。定向EvidenceRecord新增 `target_claim_fingerprint`，覆盖ID/version/text/conditions/kind而不包含evidence IDs；empirical resolution对同card/run历史版本也要求指纹匹配，防止不同卡恰好使用C1时错误继承验证。

同批修复允许pre-card请求仅绑定真实run/task，包括没有campaign的独立proposal；非空claim/issue/draw必须在冻结输入中可见。source_recheck必须使用其自身 `read_record` 的 `result.source_id`、非空content与 `arguments.record_id` 对上目标，不能只看顶层source_ids（真实read_record该字段为[]）。这批修改已通过255项整合测试；V3恢复后卡已保存；随后新颖性核查一次结构修复后仍有三个request目标均为null，最终INVALID_OUTPUT_AFTER_REPAIR，未产生accepted novelty。后续角色仍未完成。

引用正确不等于科学判断正确。[V3_EVIDENCE_REVIEW](V3_EVIDENCE_REVIEW.md)记录了原作者IoU删除公式与集合定义不符、模型颠倒下采样/形态学操作顺序、章节标错，以及“稀疏大对象”与original/inference混写等问题。18条exact只证明摘录可定位，不能证明复合主张全部成立。

卡保存暂停时V3子账户为163调用、人民币2.877053–2.887771、reserved=0；不是开发父账户总费用，也不是之后恢复的最终费用。eda3965恢复V3使用已有frame/shared/recheck/next/compose检查点，不重付这些已保存步骤；卡已保存不等于完成选择。在当时新颖性暂停时V3子账为人民币4.529248–4.539975，与前述163调用的历史卡保存停点分开；该快照没有accepted novelty。L2三入口、L3自然同卡和L4对照仍未全部完成。

`0f66f56`另修复有native tools时遗漏JSON模式：所有语义请求统一发送response_format=json_object，保留thinking/max、384000及stream，不加入tool_choice，不修改预算或单次结构修复上限。`tests/test_runtime.py` 的 test_native_tool_reasoning_association_and_trace、test_native_json_output_invalid_or_empty_keeps_single_repair_policy覆盖完整请求与非法/空正文；实际双模型联合探针随后通过。这不会把原V3失败任务变为accepted，也不保证模型科学判断正确。

`535357d`已落实claims必填、删除claim需旧version和非空说明、Runtime只核对明确结构化当前claim/issue外键；proposer自由文字不按ID猜测。read_record保留有正文来源的原文总长/完整度，另公开缓存范围；metadata-only明确无正文且重复本地读不能补出正文。对应 `tests/test_claim_targets.py`、`tests/test_runtime.py` 的 test_partial_source_cache_end_preserves_original_coverage、test_metadata_only_source_reads_expose_missing_body_without_claiming_completeness，详细原件/测试映射见 [CLAIM_AND_SOURCE_FIXES](CLAIM_AND_SOURCE_FIXES.md)。这些离线与安装结果不证明新run已避免空读循环或完成科研判断，L2/L3/L4未完成标识保持。

## bac3659 契约收口与真实恢复

| 条目 | 状态与具体证据 |
|---|---|
| §8.1 / D6 Markdown边界 | confirmed_fixed：workflows移除source_recheck内联英文问题，保留原questions与结构化失败数据；test_invalid_quote_has_one_separate_source_task_and_preserves_rejection及生产AST检查，未新增Markdown/schema。 |
| §4.2 / B5 报告继承 | confirmed_fixed：reports按实际引用解析跨run证据，不复制验证结论或引入全库；tests/test_reports.py 的 test_cross_run_report_resolves_only_referenced_inherited_evidence覆盖四种引用位置。 |
| §4.2 / §6 / B18 实际查证 | confirmed_fixed：workflows区分合法零结果搜索与注册且有非空正文/一致覆盖的读取；tests/test_evidence_gates.py 的四组反例和通过例验证fresh/novelty及恢复，空读不会满足门槛。 |
| §6 / §7 / B08 / D9 执行来源 | confirmed_fixed：runtime仅从本task成功搜索trace派生actual_searches，typed执行日志保留真实有序重复；tests/test_runtime_provenance.py 的 test_actual_search_repeated_hits_preserve_order_and_accept_without_deduplication、test_scientific_source_reference_duplicates_still_rejected、test_investigator_request_duplicate_sources_not_exempted_with_search_log。 |

首次5e3830c零调用恢复仍被duplicate_source_reference拒绝：实际工具重复命中同来源，原执行记录没有造假；旧科研引用唯一性误用于执行日志。该失败及work/recover-rendering-provenance.log保留，详情见 [SEARCH_PROVENANCE_FIX](SEARCH_PROVENANCE_FIX.md)。

`bac3659`的禁止新增模型/工具动作恢复已通过：shared_investigation为 `ACCEPTED`，error=None，19条findings已登记；原始raw及除actual_searches外的研究字段完全不变，repair_count=1，new_model_or_tool_calls=0。恢复窗口父账本保持1157调用、人民币18.981215–18.992283、reserved=0。审计路径相对于 `.arc-validation/artifacts/`：`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/implementation-fixes/bac3659512f2bae137b8a0241b71c64c17ff3549.json`；normalization审计hash为 `16cd9bf3476c7e3c032d3b24b245708b2fe9c1e63d5847a625d40a8f5be540e4`。该账本快照不包含随后已恢复的自然抽卡新增调用。

上述恢复是真实本地恢复证据，不是重新生成科研内容，也不关闭L2/L3/L4。后续自然抽卡已到卡保存及新颖性预算准入暂停；本次只勾选工程与已完成的受控恢复，在该历史时点，完整流程、质量对照及最终父账本结算尚缺验收记录；实际等待24小时、强制断网/provider断流未实测只限定证据范围，不扩大验收要求；启动SSH正常退出后的独立进程存活另已实测。

## d0d7459追加前的自然阶段与报告验证边界

Rendering自然run已保存 `card_52bce58017164c2b9594c418eb0cac7b` v1，共10条claims，题目为T-LESS固定场景外观/几何覆盖轴正交归因。frame/shared/archive/next/compose/card_archive均为ACCEPTED；draw1.novelty仍为PENDING，run停为 `PAUSED_BUDGET / budget_not_admitted`，没有accepted novelty，selector未执行。

该阶段子账为140调用、人民币4.209140–4.209176、reserved=0；剩余15.790824低于下一次Pro完整请求15.912预留。这是请求发起前的预算准入暂停，并未花完20元，也不是科研否决。父入口快照为1231调用、人民币21.887283–21.898374、reserved=0、remaining=78.101626；父余额不替代阶段独立上限，未将父账户剩余挪给该阶段。

E2E_RESULT记录L2 discover为PAUSED_BUDGET、L3为not_completed、selected_card=null。L4已按EVAL_PLAN于2026-09-07 08:11:25 UTC启动，顺序为segmentation V3、rendering、固定conflict holdout；该快照只记录启动后的运行中状态，无完整评价结果；不能由该历史记录关闭L2/L3/L4，也不将它作为追加后的最终状态。

真实报告在隔离目录重建的审计为 `work/report-check-bac3659/arc-vnext-validation-20260907.explicit_input.develop/AUDIT_RESULT.json`：7条引用均属于同一run，跨run引用数为0；研究记录hash及PAUSED_BUDGET状态保持不变。因此，本次真实重建只证明所观察报告重建不改变研究状态；跨run链接真实分支未观测，该快照仅有 `tests/test_reports.py` 的 test_cross_run_report_resolves_only_referenced_inherited_evidence 等真实Store离线回归证据。

## 启动SSH退出后的独立进程存活

真实独立进程验证见 `work/ssh-detached-verification.json`。2026-09-07 08:11:25 UTC通过nohup启动PID 3797713，启动SSH正常exit 0（退出码由主线程当时观察，审计文件明确未独立重采）。08:13:11与08:14:06 UTC的新连接均观察到PPID=1、SID=3797713，启动launcher已退出。首个ARC.frame原始请求 `call_82f4d131de9f41b6a5fca6a7dd588846` 与唯一repair `call_d83ed0a8652e4413b50fa5eeb88a6c6a` 均已完整返回并SETTLED，随后direct-Pro.compose的 `call_89dc686a52714b32aa5c72d343ff7f55` 实际进入IN_FLIGHT。它证明独立ARC进程在启动SSH正常退出后继续工作；不证明强制断网、provider流式断流恢复或实际超过24小时。

验收状态为confirmed_fixed（独立进程跨启动SSH正常退出继续运行）。首个frame的PAUSED_EXTERNAL不影响该进程存活证据，也不能被写成接受了科研frame或完成了L4。未实际等待24小时仅是证据范围说明，不是额外验收阻塞。L2/L3/L4在该历史时点未关闭，最终状态另见顶部所列记录。
