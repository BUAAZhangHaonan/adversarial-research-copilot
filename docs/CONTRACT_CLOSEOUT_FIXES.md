# 交付前契约复查修复

2026-09-07，L4与holdout运行之前，对照EXECUTION_SPEC再次检查实现。以下均来自代码和已保存开发trace，不来自holdout评价；不改变模型、强度、预算、研究题目或科学判断。

| 契约要求 | 发现的问题 | 修复及验证目标 |
|---|---|---|
| §8.1、附录D6：运行时提示词来自Markdown | source_recheck的questions列表内追加固定英文深读问题 | 移除内联指令。沿用investigator.md已有的具体问题、精确原文及来源范围规则；代码只提供原questions、失败原因、目标来源和未验证结果。Markdown/schema不改。 |
| §4.2、B5：继承证据与来源可追溯 | 报告只取当前run新建证据，可能漏掉上一阶段引用的正文链接 | 按当前run、card、issue、direction change、最终裁决和实际任务输入manifest中的引用ID取原记录。保留证据登记run，不复制验证状态，不引入全库无关材料。真实Store回归覆盖motivation/claim/issue/run四种继承引用。 |
| §4.2、§6、B18：实际查证而非正常返回即算成功 | read_web/read_paper空正文仍因completed被算为新查证 | 新门槛区分成功搜索和正文读取。搜索合法零结果只证明查过；读取必须有注册来源、非空实际正文及一致覆盖信息。空读、metadata、错误或无覆盖不能通过；原文复核仍另要求实际目标读取。 |
| §6、§11：真实执行记录可审计 | 搜索返回同来源两次命中，科研引用唯一性检查误拒执行日志 | 仅typed InvestigatorResult.actual_searches允许保留实际有序重复命中；每个来源仍验证存在，科研引用列表的重复规则保持有效。见[SEARCH_PROVENANCE_FIX](SEARCH_PROVENANCE_FIX.md)。 |

四项工程修复均为confirmed_fixed：提交 `bac3659512f2bae137b8a0241b71c64c17ff3549`，整套326 tests passed / 66.28s，日志 `work/tests-contract-closeout.log`。该HEAD的git archive源码构建wheel/sdist，独立 `.venv-wheel` 安装后从 `/tmp` 执行 `work/check_installed.py` 和 `arc --help` 均通过；日志为 `work/wheel-build-bac3659.log`、`work/wheel-install-bac3659.log`、`work/wheel-help-bac3659.log`。这些结果不证明真实入口、自然同卡链或质量对照已完成。

| 修复 | 直接回归证据 |
|---|---|
| Markdown边界 | `tests/test_validation_recovery.py` 的 test_invalid_quote_has_one_separate_source_task_and_preserves_rejection 核对原questions与失败来源仍保留；`tests/test_prompts.py` 的 test_production_prompt_boundary 检查生产调用边界。 |
| 继承报告 | `tests/test_reports.py` 的 test_cross_run_report_resolves_only_referenced_inherited_evidence，参数覆盖motivation/claim/issue/run引用，且拒绝混入无关材料。 |
| 实际查证 | `tests/test_evidence_gates.py` 的 test_empty_external_reads_do_not_satisfy_verification_or_replay、test_actual_registered_text_with_coverage_satisfies_verification、test_successful_zero_result_search_counts_as_search_not_original_read、test_read_label_and_source_id_do_not_replace_actual_body_coverage。 |
| 重复搜索命中 | `tests/test_runtime_provenance.py` 的 test_actual_search_repeated_hits_preserve_order_and_accept_without_deduplication、test_scientific_source_reference_duplicates_still_rejected、test_investigator_request_duplicate_sources_not_exempted_with_search_log。 |

`bac3659`的禁止新增模型/工具动作恢复已通过：shared_investigation为 `ACCEPTED`，error=None，19条findings已登记；原始raw及除actual_searches外的研究字段完全不变，repair_count=1，new_model_or_tool_calls=0。恢复窗口父账本保持1157调用、人民币18.981215–18.992283、reserved=0。审计路径相对于 `.arc-validation/artifacts/`：`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/implementation-fixes/bac3659512f2bae137b8a0241b71c64c17ff3549.json`；normalization审计hash为 `16cd9bf3476c7e3c032d3b24b245708b2fe9c1e63d5847a625d40a8f5be540e4`。该账本快照不包含随后已恢复的自然抽卡新增调用。

历史5e3830c已通过290项/54.28s，但首次零调用恢复仍因duplicate_source_reference暂停；原失败见SEARCH_PROVENANCE_FIX，不能用后续成功覆盖它。自然抽卡已继续，L2/L3仍待结果，L4未执行。报告继承和查证门槛的工程回归不等于已完成真实科研质量验收。
