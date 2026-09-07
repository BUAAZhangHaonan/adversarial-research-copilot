# 主张续接与缓存原文范围修复

日期：2026-09-07。状态：本批主张/来源修复的远端整套已通过283 tests / 52.08s，日志 `work/tests-claim-source.log`；源码提交为 `535357d08667ee192e246f8de0a126de0a544f0d`；其git archive已构建独立wheel/sdist，并在 `/tmp` 使用 `.venv-wheel` 验证安装资源。真实新run刚开始，尚不能宣称修复后科研E2E通过。Windows此前282 passed / 427.42s是较早快照，不是最终283项结果。本文不宣称真实L2已恢复成功。

## 真实失败与原件

对象为 `arc-vnext-validation-20260907.explicit_input.develop`，卡 `card_b63f6d85554a493a8be684fca084edd6`。详见 [L2_EVIDENCE_REVIEW](L2_EVIDENCE_REVIEW.md) 的“后续只读快照”与“NucVerse3D全文子项已关闭”部分。该输入是明确标记的软件入口验证提案，不是自然discover推荐卡。

1. v1有三个结构化claim；development原始JSON的proposed_revision没有claims键，规范化accepted与保存的v2却出现claims=[]。同一回复声称c1/c2/c3文本与版本未变；后续skeptic结构化criticism仍引用旧c2。缺字段被默认空数组掩盖，并不能解释成角色明确撤回了全部主张。
2. 对缺失当前claim的批评，旧流程没有在角色接受前严格检查其当前卡/issue归属。背景材料或旧卡里出现同名ID，不等于该ID仍是当前卡的有效目标。proposer的claims_defended等字段则本来就是论述文字，不能把这类文字误当外键。
3. NucVerse3D来源 `src_77cdc484e37a4d069ea1341c174e709a` 的registry总长为124840，保存90000，content_complete=false。skeptic以offset=68000、limit=24000实际读到22000字符。旧read_record返回content_total_chars=90000、more_content=false；总长被缓存长度覆盖。content_complete=false仍在，但角色将该窗口称为“至文末”并关闭全文缺口。既有确定性的工具语义缺陷，也有模型忽略不完整标识的问题；没有证据支持它已读完缺少的34840字符。

两个关键状态原件均相对于隔离目录 `.arc-validation/artifacts/`：

| 对象 | 原件路径与校验指针 |
|---|---|
| development | `runs/arc-vnext-validation-20260907.explicit_input.develop/tasks/b6063e58916d697ade0ea41c1ad17d5a179f2d404f7acab76370bf482e861c73/states/59e90ccb74fb42d3a712861d85d59b00.json`；SHA256 `d26f72b7f7b39c557bbd5415d0048bfebd32b8d6a9ab1131efd780fa7ca9a74a`。 |
| skeptic | `runs/arc-vnext-validation-20260907.explicit_input.develop/tasks/3dc0245403d7e96f2ad9e5b91fd69232f493d47b5e5aa7fc4f2825bc8b8b8f14/states/255c9d18d21b41a08dc625c012dfefe4.json`；SHA256 `2b441b3adb13ee2553a1a0a38a8eef955efd00601ffeb9887a0945e65a340b40`；尾段调用 `tool_1bd6b847fa0f4fa1a9cfe82958b61f45`。 |

124840来自来源registry及此前read_web元数据，不是skeptic这次收到的总长；它收到的字段已被覆盖成90000。上述原件路径和hash来自只读复核记录，本次文档更新没有重新发起研究检索或模型请求。

## 独立run的metadata-only空读失败

另一个入口 `arc-vnext-validation-20260907.explicit_input.run` 在import期间反复读取没有正文的搜索来源。2026-09-07 06:45:05 UTC固定快照最后连续215条为零正文read_record；最近40条是20个source各读2次，均offset=0、limit=3000。它们是metadata_only、content_origin=metadata、content_path=null，却带旧的content_complete=true。该40条窗口没有新search/read_web，不是正在补取缺失正文。数字是暂停前抽样，不能充作最终调用总数。

固定原件：`runs/arc-vnext-validation-20260907.explicit_input.run/tasks/7fa45215f940411069afa06bfb74a546dff464b0f25961b4a40fea0fa96d9454/states/9af411cfd953405fa824c94d0b7dfa90.json`。完整计数、示例tool/source ID及最终状态见 [L2_EVIDENCE_REVIEW](L2_EVIDENCE_REVIEW.md) 的“独立run入口”。

这次由开发者临时对单个run安装budget_calls新INSERT准入阻断，而非生产代码自动检测循环。06:48:06 UTC安装时已开始的 `call_c3532cc771304bff85d163e3aad6cb69` 完整保存并结算，之后的新工具reserve在发送前被拒绝；没有截断流式回答或更改预算。原始ERROR/IntegrityError保留在维护审计，收尾标为PAUSED_PROTOCOL / metadata_source_empty_read_loop_development_pause，临时trigger已移除。

维护原件为 `maintenance/pause-empty-read-validation-20260907.json` 与 `maintenance/pause-empty-read-validation-20260907-close.json`，均相对于同一artifacts目录。这个措施只记录本次开发暂停，不是新增生产重试上限、循环启发式或自动修复，也不证明修订后的提示词已消除重复行为。

## 当前本地实现

| 边界 | 实现与含义 |
|---|---|
| claims必须显式提供 | `src/arc/schemas.py` 的CardDraft.claims不再有默认空列表。缺键是结构错误；显式claims=[]仍可表达空集合，不通过最小长度限制强行生成主张，也不由程序补回原卡内容。 |
| 删除主张需要准确复核 | `src/arc/validation.py::validate_revision`仍检查affected_claims/evidence_review覆盖；对从旧卡删除的claim，review必须引用旧claim的version，并给出非空、非纯空白explanation。它不会将错误版本或空解释当作已说明的删除；显式合法撤回可以保留空的新列表，旧卡不覆盖。 |
| 结构化角色目标属于当前上下文 | `src/arc/validation.py::validate_role_targets`由 `runtime.py::_validate_semantics`调用。新skeptic criticism的claim_id必须属于冻结输入当前卡；若明确引用已有issue，则issue必须在当前ledger且claim_id与该issue对应，允许处理明确保留的历史issue。proposer.issue_responses只接受当前ledger的issue_id。卡ID/version与envelope不符、重复ledger issue ID均拒绝。背景证据、旧卡或自由文本里出现ID不扩大这个范围。 |
| 自由论述不是外键 | proposer的claims_defended、claims_narrowed、claims_withdrawn是自由文字，不做字符串ID猜测。该修复不通过关键词判断论证对错，也不把所有提到旧主张的自然语言都判非法。 |
| 原文总长与缓存页分开 | `src/arc/runtime.py::build_tools`中的read_record对有正文来源保留Store返回的content_total_chars、content_complete。新增cached_content_chars、more_cached_content、requires_source_fetch，删除旧more_content，不提供兼容别名。原文总长未知时仍为null，不用缓存长度代填。 |
| 缓存耗尽的后续动作 | more_cached_content仅表示还有本地缓存页；requires_source_fetch只在content_complete=false且当前页已到缓存尾时为true。它是缺失原文提示，不会自动发请求。`prompts/tools/read_record.md`追加Cached source coverage，说明需用实际可用工具补取或保留访问限制，不能把本地缓存尾当全文尾。 |
| metadata-only明确没有正文 | `src/arc/runtime.py`的新搜索来源登记以bool(text)作为content_complete缺省值。read_record遇到旧无正文source，即使旧记录complete=true，也明确返回content=null、content_complete=false、cached_content_chars=0、more_cached_content=false、requires_source_fetch=true；不把snippet当正文，不改写旧来源记录。Markdown说明重复本地读取不会补出正文，需要实际可用的原文获取工具或保留访问限制。 |

这里的claim外键检查范围是proposer/skeptic明确声明的结构化目标；其他角色已有的来源、证据、finding目标、请求归属及moderator ledger校验继续由各自契约承担，不声称一次helper覆盖所有科学语义。

## 回归证据与验证状态

下列测试已在当前本地文件中定位；主线程远端最终整套结果为283 passed / 52.08s，本次文档更新没有再执行suite。已提交为535357d；离线通过不等于旧付费任务已经恢复成功。

| 测试文件 | 针对性反例 |
|---|---|
| `tests/test_claim_targets.py` | test_omitted_revision_claims_are_not_silently_converted_to_withdrawal；test_deleted_claim_review_requires_old_version_and_real_explanation；test_explicit_claim_withdrawal_preserves_original_and_allows_empty_revision。分别区分缺字段、非法删除复核与合法显式撤回。 |
| `tests/test_claim_targets.py` | test_real_shape_empty_current_claims_and_no_issues_rejects_old_criticism；test_skeptic_current_claim_and_explicit_existing_historical_issue_are_valid；test_skeptic_existing_issue_must_belong_to_ledger_and_match_its_claim；test_proposer_only_explicit_issue_ids_are_checked_not_claim_prose；test_role_target_card_is_the_enclosing_subject_and_ledger_ids_are_unambiguous。 |
| `tests/test_runtime.py` | test_partial_source_cache_end_preserves_original_coverage覆盖缓存前页、68000尾页和缓存外90000空页；test_unknown_original_length_is_not_replaced_with_cache_length保留未知总长；test_service_adapter_registers_original_without_truncating_paper提供完整原文读尾对照。 |
| `tests/test_runtime.py` | test_metadata_only_source_reads_expose_missing_body_without_claiming_completeness覆盖旧complete=true、没有正文的来源在重复本地读取时仍明确缺正文且不改原记录；test_service_search_snippet_stays_metadata检查新搜索记录的来源层级、完整度和未知正文总长。 |
| `tests/test_prompts.py` | test_spec_assets_are_exact核对27份原稿。当前23份全文相等；developer、investigator、output_protocol、read_record四份保留原稿完整前缀后追加。协议追加见 [PROMPT_INVENTORY](PROMPT_INVENTORY.md)。 |

未关闭的边界：修复后的真实研究输出与恢复结果仍需单独记录；尤其没有真实结果证明新metadata说明已阻止空读循环。原始付费回复、accepted对象、卡v2和来源证据不人工补回、不覆盖，也不因新规则存在就追认旧结果正确。

这些修复约束数据完整性和读取范围，不会自动纠正L2抽查中IoU数值被推成几何覆盖、SoftPQ条件扩大等科学推断。修复通过后仍不能仅凭结构合法或可定位摘录声称idea质量提高，L2/L3/L4的完成状态由真实验收报告另行记录。

源码535357d的独立安装日志为 `work/wheel-build-535357d.log`、`work/wheel-install-535357d.log`、`work/wheel-help-535357d.log`。本次文档更新起点为3f6026f；这三个安装结果与283项工程测试均不能把旧paid任务改成成功，L2/L3/L4尚未完成。
