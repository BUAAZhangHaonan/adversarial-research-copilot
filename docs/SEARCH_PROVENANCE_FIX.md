# 检索执行记录的机械来源修复

日期：2026-09-07。最新代码 `bac3659512f2bae137b8a0241b71c64c17ff3549` 已通过326项测试（66.28s）及独立wheel/sdist安装验证，禁止新增模型/工具动作的真实恢复已接受调查并登记19条findings。历史 `5e3830cc65d462afb6420ae9860d57e4f7b55aaf` 的290项测试（54.28s）和独立安装验证仍保留；它的首次真实恢复曾停于 `duplicate_source_reference`，不能回写为当时成功。

## 真实失败

Run为 `arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover`，当时暂停task为 `.shared_investigation`，历史停点为 `PAUSED_PROTOCOL / unknown_source_id`、accepted_result=null。子账人民币1.303072–1.303085，66次账本调用，reserved=0。独立冻结审查见 [RENDERING_EVIDENCE_REVIEW](RENDERING_EVIDENCE_REVIEW.md)。

| 对象 | 原始记录 |
|---|---|
| 修复后模型声明 | `$.result.actual_searches[1].source_ids[5]` 为 `src_d981b8788f84791b2af69a2f07ae529`。 |
| 本task实际搜索 | `tool_a18a8794e6dc476a836949b39cd63b2d` 的source_ids[5]与result.sources[5].source_id均为 `src_d981b87884f84791b2af69a2f07ae529`。 |
| 原始生成/唯一结构修复 | `call_5d438dbd7de24eaf9fb92f38d6173a6b` / `call_2600f86e41dd415d939aa609d75f6af4`。原始生成有JSON尾部及字段结构问题；来源ID的漏字是在该次repair中出现。 |
| 冻结状态 | 相对于 `.arc-validation/artifacts/`：`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/tasks/805c7f22e9760ba8422b8da3052a3b42eac47ed7eb5f3d32959f12ed60a99292/states/f646be8120474ba0b3e8d90afd7a22fc.json`；SHA256 `b948a0b6f2cba11bc33c124cb5123ac301a9f79078cc6066889c74e326f9aa98`。 |

18条actual_searches与成功搜索的trace ID、operation、query、有序source ID列表逐项对照，仅上述一个ID不同。真实ID已注册，是一次无关网页命中的metadata；没有证据支持来源注册器丢失了它。19条findings涉及13个来源，摘录均在各自保存正文中唯一匹配，也出现在本task实际返回的正文中，但在该历史停点尚未登记。这个结论只核对引用，不代替科学范围判断。

## 任务书依据与修改范围

| 依据 | 本项对应的执行边界 |
|---|---|
| §6：工具方法/参数由实际能力与代码核验，稳定ID和工具返回有确定来源 | 搜索是否发生、提交了什么query、返回哪些source ID属于执行事实。actual_searches应从本task的成功搜索trace机械派生，无需模型再次抄写这些字符串，也不根据模型文字推测发生过搜索。 |
| §7.4：成功响应已保存后，解析/渲染失败在本地恢复，不重复付费 | 保留初次raw、唯一repair、工具返回、旧失败状态与账本。新增派生和审计从保存响应与trace计算，不为了修复抄写错误重新检索或生成整份科学调查。恢复仍必须通过其余schema、来源、引用、原文与任务归属校验。 |
| §11与附录B5/B6：实际trace、原件、分层验收，不造E2E成功 | 独立审计同时保存模型声明与执行记录，说明本次只改变机械provenance。验证恢复是否未重复付费、研究字段是否未变；接受该调查也不能直接宣布研究卡值得做或L3完成。 |

这不把§6解释成可自动改写任意证据。finding的source_id、excerpt、claim、conditions、relation、origin及科学解释仍由原输出承担，错误仍拒绝。没有从相似ID里选一个“可能正确”的来源，也没有把所有已注册来源都塞进本任务可见集合。

## 已实现的机械派生与审计

本地 `src/arc/runtime.py` 的 `derive_investigator_searches` 仅处理InvestigatorResult：从当前task已完成的search_web/search_literature依执行顺序构造SearchTrace，复制call_id、操作名、实际提交query/theme_document与source_ids。read_*、档案读取和失败动作不算成功搜索；task/run不匹配和重复trace ID拒绝。它生成单独的派生对象，不覆盖模型原始回复。

`Runtime._normalize_search_provenance` 对剔除actual_searches后的完整候选计算前后hash，要求其余字段完全一致。这里比较的是本次结构修复后已解析候选，不是宣称初次非法JSON与repair逐字相同。独立normalizations审计记录输入状态指针、响应call ID、raw内容hash、原始模型声明、权威actual_searches、实际trace/hash及研究字段前后hash。已保存审计的内容或依赖不一致时应拒绝恢复；旧accepted原件不被覆盖为一个伪装的新模型输出。

5e3830c的回归覆盖旧repair恢复、科研来源/引文错误仍拒绝、缓存accepted不重写、跨任务隔离、审计写出后checkpoint中断的幂等恢复。远端整套290项通过，日志`work/tests-provenance.log`；独立安装包日志`work/wheel-*-5e3830c.log`。这是5e3830c的历史验证，不包括后续重复命中窄修复。

首次真实零调用恢复记录在`work/recover-rendering-provenance.log`。实际工具返回的`actual_searches[5].source_ids`有同一来源`src_48b4ff39da4d46ecb4f9afcbc8cb6c8a`的连续两次命中；模型与派生日志均忠实保留，但旧科研引用唯一性检查错误地拒绝了执行日志。后续修复限定为执行日志允许实际重复命中，每个ID仍验证存在，科研引用重复规则不放宽。父账本保持1157调用、18.981215–18.992283元、reserved=0；没有为此重搜或重生成。

## 针对性验收

- [x] 5e3830c代码回归：只选本task/run的成功search，保留实际query和有序返回ID；失败/read_*排除，外来或重复trace拒绝。重复hit窄修复另由bac3659整合验收。
- [x] 5e3830c不变性回归：只有actual_searches机械字段被派生；finding及其余研究字段、初次raw、唯一repair和旧产物不变；研究引用真正错误时仍被拒绝。
- [x] 5e3830c独立审计与恢复回归：原模型声明、执行事实、来源状态及hash可追溯；重复本地恢复不重发成功工具或模型请求，不增加repair次数，不重置费用。
- [x] bac3659整合验证：326 tests / 66.28s，`work/tests-contract-closeout.log`；从该HEAD源码归档构建wheel/sdist，独立安装及仓库外资源/CLI验证通过。
- [x] Rendering真实受控恢复：候选通过剩余校验后，shared_investigation为ACCEPTED，登记19条findings；新增模型/工具调用为0，单次repair及研究原件保留。

`bac3659`的禁止新增模型/工具动作恢复已通过：shared_investigation为 `ACCEPTED`，error=None，19条findings已登记；原始raw及除actual_searches外的研究字段完全不变，repair_count=1，new_model_or_tool_calls=0。恢复窗口父账本保持1157调用、人民币18.981215–18.992283、reserved=0。审计路径相对于 `.arc-validation/artifacts/`：`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/implementation-fixes/bac3659512f2bae137b8a0241b71c64c17ff3549.json`；normalization审计hash为 `16cd9bf3476c7e3c032d3b24b245708b2fe9c1e63d5847a625d40a8f5be540e4`。该账本快照不包含随后已恢复的自然抽卡新增调用。

安装日志：`work/wheel-build-bac3659.log`、`work/wheel-install-bac3659.log`、`work/wheel-help-bac3659.log`。重复hit回归为 `tests/test_runtime_provenance.py` 的 test_actual_search_repeated_hits_preserve_order_and_accept_without_deduplication；test_scientific_source_reference_duplicates_still_rejected 和 test_investigator_request_duplicate_sources_not_exempted_with_search_log 保持科研/请求引用唯一性。

后续自然抽卡已resume，仍待结果。恢复调查只关闭本项机械来源与零新增调用恢复验收。

本项不增加科研任务、不改品味规则、不改预算，也不把机械恢复当成模型科学判断变好。L2/L3/L4及真实研究结论继续由各自实际产物验收。
