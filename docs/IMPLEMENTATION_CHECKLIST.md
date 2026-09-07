# ARC execution checklist

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

Contract: `EXECUTION_SPEC.md` (2026-09-06), including appendices A–D.
Baseline: `3bc93dd0be54d3c2ffc4c2b4f9f2014c79064c85`, clean master on g203.
Isolated branch: `codex/arc-vnext-20260907`; worktree `/home/g203/zhanghaonan/arc-vnext-20260907`.

- [x] A0 Read contract; audit live baseline, preserve main checkout and user data.
- [x] A1 Strict shared entities, role results, envelope, single decision protocol.
- [x] A2 All 27 Appendix A Markdown assets, manifest, package-safe loader and snapshots.
- [x] B1 SQLite authoritative research state, immutable versions, evidence and Chinese archive.
- [x] B2 Persistent CNY request reservations, 20 CNY default stages and single 100 CNY validation parent; later three-account exceptions are recorded separately in BUDGET_EXTENSION_AUTHORIZATION.
- [x] B3 SDK model adapter, max thinking, full output ceiling, native tools, strict completion and recovery.
- [x] B4 Official MCP SDK, actual capabilities, source registry, read-only permissions and bounded costs.
- [x] B5 Deterministic Chinese reports, trace/cost indexes and reconstructable views.
- [x] C1 discover: shared investigation, at most five paid draws, substantive archive comparisons.
- [x] C2 develop: inherited evidence, fresh verification, immutable anchored revision, frozen scope change.
- [x] C3 run: single issue kernel, complete transitions, targeted retrieval and experiment handoff.
- [x] C4 CLI defaults stop, import/status/resume/authorized budget additions/explicit E2E transition.
- [x] D1 B01–B18 replacement implementation and section 11 deterministic engineering coverage; independent installed CLI outside repository. Normal SSH-launcher exit survival is verified separately in D7; forced network/provider stream interruption and elapsed-24-hour tests are not covered.
- [x] D2 Commit the bounded V3 source_recheck path in acc012a; its integrated suite passed 238 tests.
- [x] D3 Commit background-evidence bindings, exact target fingerprints, pre-card request visibility and read_record target matching in eda3965; 255 integrated tests passed.
- [x] D4 Commit JSON/native-tools compatibility in 0f66f56; 263 tests/48.55s and independent wheel/sdist installation checks passed.
- [x] D5 Commit claim continuity, structured role targets, partial-cache and metadata-only source fixes in 535357d; 283 tests/52.08s plus independent wheel/sdist installation checks passed.
- [x] D6 Commit mechanical search provenance and closeout contracts in bac3659; 326 tests/66.28s and controlled-source independent wheel/sdist installation checks passed. Historical 5e3830c passed 290/54.28s before the repeated-hit fix.
- [x] D7 Real independent ARC process survived normal exit of the launching SSH connection, completed the original response plus one repair, and began direct-Pro.compose. Evidence: work/ssh-detached-verification.json; this does not cover forced network loss, provider stream interruption, or 24-hour uptime.
- [x] E0 Freeze evaluation plan, topics, holdout, one parent budget and comparison rules.
- [x] E1a Live Flash/Pro max protocol, MCP tool traces and saved-response resume. Both JSON/native-tools joint probes completed with two model calls, one real read_record, zero repairs and final stop each.
- [ ] E1b Three real entry points and issue-linked additional evidence (L2).
- [x] E1c V3 source_recheck accepted 18 strictly matched findings after actual saved-source reads; preserve the rejected shared task. This is not acceptance of all scientific claims.
- [ ] E1d Finish subsequent real V3 roles after eda3965. Card-save recovery succeeded; novelty stopped at INVALID_OUTPUT_AFTER_REPAIR after one structural repair. No accepted novelty exists, and selection/develop/run remain pending.
- [x] E1e Guarded rendering shared_investigation recovery on bac3659 accepted and registered 19 findings with zero new model/tool calls; raw/research fields except actual_searches and the sole repair remain unchanged. This does not complete the discover stage or L2.
- [ ] E2 Natural same-card discover/develop/run (L3), or explicitly document external blocker.
- [ ] E3 Fixed-material direct-Pro comparison, holdout and anonymous evaluation (L4). Started per EVAL_PLAN at 2026-09-07 08:11:25 UTC in order: segmentation V3, rendering, fixed conflict holdout; the d0d7459 record had no completed comparison result; final continuation outcomes are recorded separately.
- [ ] F Clean replaced production code, dependency lock, migration, audit/cost/E2E docs, local commits.

Completion requires code and relevant tests per requirement. L1/L2/L3/L4 are reported separately.
Unknown external service charges block their paid actions; they do not count as zero or successful E2E.
No push, no research experiments, no changes to reference or MCP repositories.

Engineering snapshot retained at d0d7459 (before budget extensions): bac3659512f2bae137b8a0241b71c64c17ff3549, 326 tests passed in 66.28s, log work/tests-contract-closeout.log; wheel/sdist built from that git archive and installed-resource/CLI checks from /tmp in .venv-wheel passed. Historical snapshots: 5e3830c (290/54.28s, work/tests-provenance.log, independent installation passed), 535357d (283/52.08s, work/tests-claim-source.log), 0f66f56 (263/48.55s), 2b8b79a (258/46.23s), eda3965 (255/47.29s). Windows 282/427.42s was an earlier snapshot, not the final source-fix suite.

Documentation closeout against the complete contract:

- [x] Sections 0–12 mapped to current files and tests in IMPLEMENTATION_AUDIT, including section 9 default roles and section 10 B01–B18. Replaced old code is not described as a reproduced old failure.
- [x] All ten section 11 matrix rows name actual test functions and explain what synthetic/offline checks do not prove.
- [x] Appendix A lists all 27 assets: 23 exact files and four preserved full original prefixes in developer/investigator/output_protocol/read_record. The read_record Cached source coverage and metadata-only additions are included in the 535357d suite; historical test counts do not retroactively cover later changes.
- [x] Appendix B1–B6 maps envelope, thirteen result contracts, card/cost fields, assembly, observability and acceptance levels separately.
- [x] Appendix C retains official/community/reference evidence levels and all six actual reference projects; Kaimen Co-Scientist is explicitly unofficial.
- [x] Appendix D1–D12 maps each final statement to engineering evidence and leaves unfinished real acceptance open.
- [x] bac3659 controlled-source wheel/sdist build and separate installation checked from /tmp: version 0.2.0, 15 semantic prompts, packaged report/config assets, OpenAI 2.54.0 and MCP 2.1.1. Logs: work/wheel-build-bac3659.log, work/wheel-install-bac3659.log, work/wheel-help-bac3659.log; installed checks: work/check_installed.py.
- [x] Record normal SSH-launcher exit survival using real PID/PPID/SID and settled-response evidence from subsequent SSH connections.
- [x] Remove arbitrary 24-hour expiry and test saved-response recovery with old timestamps and a rebuilt runtime: test_response_saved_survives_parse_failure_and_old_date and test_response_saved_before_validation_recovers_locally_after_long_pause. These are engineering recovery tests, not a claim of physically waiting 24 hours; the contract does not add that wait as a separate release blocker.
- [ ] Complete real L2/L3/L4 evidence and final parent-account cost closure; do not use the static mapping or the old ACCEPTANCE_BOUNDARIES draft as a current completion claim.

Audit status labels distinguish confirmed_fixed, already_fixed, replaced, not_reproduced and blocked. Here blocked means missing acceptance evidence, not necessarily a paused live process. Existing CLI entry points are resume for a saved stage, test-e2e --allow-stage-transition for the authorized same-card chain, and test-compare --source-run for frozen-material comparison. These are remaining verification entries, not commands executed by this documentation review. Development calls must continue using the original validation database and 100 CNY parent account.

V2 retained its accepted response and raw artifacts. Offline original-source revalidation ended at PAUSED_PROTOCOL / excerpt_not_in_returned_source, with no new requests; the parent ledger at that point contained 141 calls and CNY 2.480237–2.480271. This is not a cost total including subsequent V3 work.

V3 history: its original final reply was not JSON. One structural repair returned complete, but preliminary requests lacked claim/issue/draw ownership and one of 17 quotations changed mathematical notation to 20x. The original shared task remains PAUSED_PROTOCOL. A separate source_recheck is now ACCEPTED with 18 exact quotations; Nature material was actually read three times. See E2E_REPORT for call IDs and work/v3-recheck-audit.json for the read-only audit record.

Recorded card-save stop: draw1.next and COMPOSE were accepted, but save_card paused with claim_evidence_version_mismatch. The draft has seven new clm_meas_01..07@1 claims and nine cross-ID background references, not old-version inheritance. Commit eda3965 allows those explicit background bindings without transferring verification, retains same-ID version checks, and requires a target fingerprint for empirical resolution, including historical versions in the same card/run. Pre-card requests need a real run/task; any supplied claim/issue/draw must be visible in frozen input. Source recheck must match its own read_record result source/content and argument record ID to the target. Raw outputs, the rejected task, old drafts and evidence are not manually rewritten.

At that historical pause, the V3 child-account snapshot was 163 calls, CNY 2.877053–2.887771, reserved=0. It is neither the parent total nor a final total after the new resume. Existing frame/shared/recheck/next/compose checkpoints are reused without paying again for saved steps. The card is now saved, but novelty stopped after one repair with three unbound request targets; no accepted novelty exists. At this later stop the V3 child cost was CNY 4.529248–4.539975. V3_EVIDENCE_REVIEW records mathematical, operation-order, section and scope/origin problems despite exact quotations. L2/L3/L4 remain incomplete; 18 matches and passing offline tests do not establish research quality or a completed three-stage chain.

Historical real L2 state at d0d7459, before budget extensions: explicit_input.develop is PAUSED_BUDGET after spending CNY 4.106986–4.107017. Its remaining CNY 15.892983 is below the next Pro reservation of CNY 15.912, so round 1 moderator is unfinished. This is admission control before a new request, not an interrupted active answer or a scientific rejection. The old independent explicit_input.run ended in a documented PAUSED_PROTOCOL after metadata-only empty reads; its temporary per-run INSERT gate has been removed. It did not alter the budget or interrupt an already started call, and it is not production automatic loop detection. The rendering run recovered its shared investigation on bac3659, accepted 19 findings and saved a natural card; draw1.novelty remains PENDING after PAUSED_BUDGET admission control, and selector has not run. No complete stage or chain result is recorded here. These labelled software inputs do not constitute the natural-card L3 chain.

Both joint model probes completed under the same original 100 CNY parent: JSON/native tools/thinking max/384000/stream, two model calls plus one actual local read_record each, repair_count=0 and final finish_reason=stop. Their protocol success leaves E1b/E1d/E2/E3 unchecked. L2 final outcomes and issue-linked new evidence, L3 natural same-card completion, L4 frozen-material comparison and the final parent cost report remain outstanding.

Rendering recovery history: the first source-ID omission pause retained its raw response, sole repair and 19 unregistered findings. The first guarded resume on 5e3830c then failed with duplicate_source_reference because the actual search returned an ordered repeated hit. Both failures remain in SEARCH_PROVENANCE_FIX and E2E_REPORT. The bac3659 guarded resume accepted the investigation without new model/tool calls, and only actual_searches changed. Parent snapshot during that guarded recovery: 1157 calls, CNY 18.981215–18.992283, reserved=0; it is not the cost total after later draws. Audit under .arc-validation/artifacts: `runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/implementation-fixes/bac3659512f2bae137b8a0241b71c64c17ff3549.json`; normalization hash `16cd9bf3476c7e3c032d3b24b245708b2fe9c1e63d5847a625d40a8f5be540e4`. E1b/E1d/E2/E3 and final closeout remain unchecked.

Historical rendering stop at d0d7459, before budget extensions: natural card `card_52bce58017164c2b9594c418eb0cac7b` v1 has 10 claims, titled T-LESS固定场景外观/几何覆盖轴正交归因. frame/shared/archive/next/compose/card_archive are ACCEPTED. draw1.novelty is PENDING; run is PAUSED_BUDGET / budget_not_admitted, with no accepted novelty or selector execution. Child snapshot: 140 calls, CNY 4.209140–4.209176, reserved=0, remaining=15.790824 < next Pro reservation 15.912. This is not spending the full 20 CNY or a scientific rejection. Parent entry snapshot: 1231 calls, CNY 21.887283–21.898374, reserved=0, remaining=78.101626; no parent balance was transferred into the stage limit. E2E_RESULT: L2 discover PAUSED_BUDGET, L3 not_completed, selected_card=null. At that recorded point L4 had started in the frozen planned order without a completed comparison result; E1b/E1d/E2/E3/F remain unchecked.

真实报告在隔离目录重建的审计为 `work/report-check-bac3659/arc-vnext-validation-20260907.explicit_input.develop/AUDIT_RESULT.json`：7条引用均属于同一run，跨run引用数为0；研究记录hash及PAUSED_BUDGET状态保持不变。因此，本次真实重建只证明所观察报告重建不改变研究状态；跨run链接真实分支未观测，该快照仅有 `tests/test_reports.py` 的 test_cross_run_report_resolves_only_referenced_inherited_evidence 等真实Store离线回归证据。

真实独立进程验证见 `work/ssh-detached-verification.json`。2026-09-07 08:11:25 UTC通过nohup启动PID 3797713，启动SSH正常exit 0（退出码由主线程当时观察，审计文件明确未独立重采）。08:13:11与08:14:06 UTC的新连接均观察到PPID=1、SID=3797713，启动launcher已退出。首个ARC.frame原始请求 `call_82f4d131de9f41b6a5fca6a7dd588846` 与唯一repair `call_d83ed0a8652e4413b50fa5eeb88a6c6a` 均已完整返回并SETTLED，随后direct-Pro.compose的 `call_89dc686a52714b32aa5c72d343ff7f55` 实际进入IN_FLIGHT。它证明独立ARC进程在启动SSH正常退出后继续工作；不证明强制断网、provider流式断流恢复或实际超过24小时。

在该历史快照中，首个L4 ARC.frame的PAUSED_EXTERNAL属于技术失败，完整对照尚无结果；D7仅证明SSH正常退出后的独立进程存活。L2/L3/L4的未勾选状态保留为当时记录。未实际等待24小时是验证范围说明，不作为额外待办或发布阻塞。
