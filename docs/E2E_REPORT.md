# 真实验收记录

记录边界：本页工程证据及运行状态保留为 `d0d7459` 文档时点的历史记录，截止三笔预算追加之前；“暂停”“运行中”和未勾选项均指该时点，不代表最终续跑结果。最新执行状态与费用以 `docs/VALIDATION_SNAPSHOT.json`、`docs/COST_REPORT.md`、`docs/L4_REPORT.md` 及最终续跑记录为准；相应最终材料未落地前不预填结果。三笔追加授权见 [BUDGET_EXTENSION_AUTHORIZATION.md](BUDGET_EXTENSION_AUTHORIZATION.md)。

d0d7459归档的工程验证：`bac3659512f2bae137b8a0241b71c64c17ff3549`，326 tests passed / 66.28s，日志 `work/tests-contract-closeout.log`；git archive源码构建的wheel/sdist、独立安装及 `/tmp` 资源/CLI检查均通过。Rendering调查的零新增调用恢复已成功，19条findings登记。历史5e3830c的290项/54.28s及首次 `duplicate_source_reference` 恢复失败保留在下文。

本文件按层级分开工程契约、真实接口、自然研究卡贯穿和自动质量对照。自动判断不是人类认可，PROMISING 不是实验成功。本报告中的独立原文复核由Codex检查已保存材料完成，也不代表人类研究者认可。

截至d0d7459文档时点、三笔预算追加前：Flash/Pro JSON加原生工具联合真实probe均COMPLETED。V3自然卡已保存，但novelty一次结构修复后仍为INVALID_OUTPUT_AFTER_REPAIR，没有accepted novelty。明确标记的软件输入develop停于预算准入，独立run因反复空读在新请求边界由开发者暂停。Rendering shared_investigation在bac3659下由已保存响应与实际搜索trace恢复为ACCEPTED；原raw及研究字段不改，只机械派生actual_searches，未新增模型/工具调用。随后自然卡v1已保存，draw1.novelty在PENDING时因阶段预留不足停为PAUSED_BUDGET，selector未执行。L4已按计划启动，首个segmentation ARC.frame技术暂停，direct-Pro在冻结快照中仍运行，尚无完整对照结果；L2未全部完成，L3未完成，L4未完成。

## L1：工程与安装包

- 该历史文档对应的代码快照：`bac3659512f2bae137b8a0241b71c64c17ff3549`，326 tests passed / 66.28s，日志 `work/tests-contract-closeout.log`。由该HEAD的git archive构建wheel/sdist，在独立 `.venv-wheel` 安装并从 `/tmp` 运行 `work/check_installed.py` 与 `arc --help` 均通过；日志 `work/wheel-build-bac3659.log`、`work/wheel-install-bac3659.log`、`work/wheel-help-bac3659.log`。
- 历史快照：`5e3830cc65d462afb6420ae9860d57e4f7b55aaf`，290 tests / 54.28s，`work/tests-provenance.log`及 `work/wheel-*-5e3830c.log` 记录整套与独立安装通过。
- 历史快照：`535357d`，283 tests passed / 52.08s，日志 `work/tests-claim-source.log`。该HEAD经git archive构建wheel/sdist并独立安装，从 `/tmp` 验证CLI和包资源；日志 `work/wheel-build-535357d.log`、`work/wheel-install-535357d.log`、`work/wheel-help-535357d.log`。Windows此前快照282 tests / 427.42s不作为最终283项的记录。
- 历史快照：`0f66f56`，263 tests passed / 48.55s，远端日志 `work/tests-json-tools.log`。该HEAD独立wheel验证通过，日志为 `work/wheel-build-0f66f56.log`、`work/wheel-install-0f66f56.log`、`work/wheel-help-0f66f56.log`。源码归档构建后在独立 `.venv-wheel` 安装，从 `/tmp` 检查CLI、0.2.0版本、prompt/报告/配置资源，避免仓库cwd掩盖漏打包。
- `2b8b79a` 固定comparison.boundaries与shuffle_seed，并追加公共请求归属说明；对应258 tests / 46.23s，日志 `work/tests-evaluation-ownership.log`。冻结相同材料和匿名顺序是工程能力，此时并未运行L4质量对照。
- 历史快照 `eda3965`：255 tests / 47.29s，日志 `work/tests-claim-bindings.log`，独立wheel验证通过。它修复背景证据绑定与目标指纹，后续V3卡保存恢复成功。
- 历史快照 `acc012a`：238 tests passed / 43.04s。
- 历史快照 `a8ddc5a`：220 tests passed / 42.42s，并完成独立 wheel 验证。
- 历史快照 `b7b3df9`：211 passed / 41.90s（g203，Python 3.13.5）。该次从受控源码归档构建 wheel，在独立 `.venv-wheel` 安装，工作目录 `/tmp`；`arc --help`、0.2.0 版本一致性、登记 prompt loader 及报告资源加载通过；OpenAI 2.54.0、MCP 2.1.1。原基线87项通过同样仅是历史背景。
- 核心提交：66d998f；快照/继承/包资源：c09e0b9；真实本地读取与原文缓存修复：2f76f4c。修复后的完整测试日志：`work/final-tests.log`。
- 离线覆盖 B01–B18 的证据映射见 IMPLEMENTATION_AUDIT。模拟/合成 fixture 不冒充真实研究证据。

## L2历史记录：接口与恢复部分已完成，三入口在当时尚未完成

早期两次真实协议probe均使用max、thinking enabled、384000输出上限、完整流式usage和JSON协议；没有发送thinking模式不接受的tool_choice。响应均stop，返回模型别名与请求一致。别名不能单独证明实际模型权重版本。这是早期无联合工具要求的探针记录，后来的完整组合验证单独列在下表之后。

| 模型 | 输入 cache miss | 输出（含 reasoning） | usage 复算人民币 |
|---|---:|---:|---:|
| deepseek-v4-flash | 4486 | 7790 | 0.083568 |
| deepseek-v4-pro | 4484 | 2534 | 0.108774 |

原件：`.arc-validation/artifacts/runs/arc-vnext-validation-20260907.protocol.MODEL/`。具体请求/响应路径由各 TaskRecord 和逐调用账本关联；原始 reasoning 不进此报告。

实际 MCP initialize/tools/list 已验证3个服务，真实 web_search/fetch_page 已通过 ARC 原生 tool loop 保存来源/全文/trace；部分外站403/SSL错误原样记为访问限制。收费 ScholarTrace.query 因缺可靠费用上界未执行，见 MCP_REQUIREMENTS。

`0f66f56` 的联合probe验证同一任务中的JSON、thinking/max、384000、stream及native tools，每模型均先实际调用一次 `read_record`，再返回最终JSON；两次模型请求、一次本地工具调用，repair_count=0、最终finish_reason=stop，run均COMPLETED。

| 模型 | 实际read_record tool ID | 子账户费用区间（人民币） |
|---|---|---:|
| Flash | `tool_0e29f9f6184e479d85e52e53a5b82a88` | 0.019979–0.019981 |
| Pro | `tool_9c602b05670c49f1bed582498f77f99f` | 0.077400–0.077402 |

两子账户为 `arc-vnext-validation-20260907.protocol_json_tools.deepseek-v4-flash` / `deepseek-v4-pro`，都归属原100元父账户 `arc-vnext-validation-20260907`，各20元上限，结束时reserved=0。日志为隔离目录 `work/live-joint-probe.log`；各run的原件位于 `.arc-validation/artifacts/runs/<run_id>/joint-protocol-audit.json`，包含模型request ID、tool ID与联合请求断言，完整ID亦见 [JSON_TOOL_PROTOCOL](JSON_TOOL_PROTOCOL.md)。读取的是当前run元数据，用于证明工具协议，不是额外科研文献证据，也不能代替三入口数据链或idea质量验收。

## 第一轮失败与纠正

`arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION.discover` 在来源登记处暂停，没有生成研究卡。webresearch 第一次返回7000字符前缀+27字符截断标记，第二次返回67082字符全文。旧登记把标记当原文，导致同来源冲突。

两次成功远端返回都仍在。一次性纠正严格核对原raw、representation hash、旧正文hash和已有引用，剥离协议标记后按同representation扩展；保留旧错误原件。恢复脚本发送0个请求；原工具费上界0元。纠正记录位于该run的 `corrections/tool_72d9e965961e4383ba6994436b9c217b.source-correction.json`。

由于 Finding 协议增加目标claim/version，旧任务恢复明确返回 `TASK_DEPENDENCY_CHANGED_FORK_REQUIRED`，不是静默更新旧任务。恢复前后调用总数保持45，累计人民币区间仍为0.747036–0.747044。

## 第二轮：明确的新版本

`arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V2.discover` 复用第一轮已登记原始材料，保留主题；不继承判断、通过状态或抽卡配额。`input-transfer.json` 记录转移边界，仍受同一100元父账户约束。

第二轮又暴露 `read_record(campaign_id)` 类型未覆盖的问题。它属于本地读取失败，不能视为远端生成丢失。补齐campaign/run摘要/issue读取后，从原工具检查点继续；未知ID返回明确工具错误，不伪造记录。本次仅处理已有本地信息，已完成搜索不重发。修复commit及未改变schema/prompt/model的事实记于该run的 `implementation-fixes/2f76f4c9f9e1a714802117b31ddf479b93a3490a.json`。

第二轮共享调查还遇到摘要页与正文表示冲突：已有 `https://arxiv.org/abs/2306.16132` 是3429字符的摘要/站点页，本次 `https://ar5iv.labs.arxiv.org/html/2306.16132` 是20000/40835字符的正文。修复 b7b3df9 将唯一身份细化为 canonical/version/origin/representation；两份原文和引用独立保留，但共同归属同一论文。工具返回也明确展示 canonical_id，不能把两表示算作独立文献。

开发验证库只重建来源唯一约束；全表逐行hash、201条source ID/JSON、账本与研究历史均不变，foreign_key_check/integrity_check通过。完整备份在 `.arc-validation/backups/source-constraints-20260907T033403919560Z.sqlite`；审计位于 artifacts 的 `maintenance/source-constraints-20260907T033403919560Z.json`。失败调用 `tool_1b6022b9e50d4fbda52da37761958f70` 的raw被本地重解析，不重发MCP；任务schema/prompt/model/effort均未改变。

以上为V2调查过程中的历史修复。其后历史停点及V3已观察到的失败见下文；在d0d7459时点没有完成自然卡三阶段链，也没有完成L4，不能将这些接口成功写成L2三入口或L3/L4通过。

## V2证据失败与V3校准验证

共享调查最终返回13条findings与2条contrary_findings；其中仅2条摘录是对应已存正文的连续原文。多数失败来自省略号拼接和改写，两条仅有search metadata/snippet。原文实质抽查还发现跨指标/条件的过度外推。详见 [PROMPT_CALIBRATION.md](PROMPT_CALIBRATION.md) 和 [SOURCE_SPOTCHECK.md](SOURCE_SPOTCHECK.md)。这属于开发失败记录，不是科学否决，更不是已有合格研究卡。

修复a8ddc5a把来源校验置于Task accepted之前，整批证据预检后才事务落盘。旧V2的accepted与raw均不篡改；使用只读saved trace和已缓存结果离线重验，运行状态从ERROR明确为PAUSED_PROTOCOL/excerpt_not_in_returned_source，账本仍141调用、累计2.480237–2.480271元，新增请求0。这是V2离线复核时点的父账户快照，不是包含后续V3的最新总费用。审计原件为该run的 `corrections/evidence-prevalidation.json`。

V3：`arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover`。它在同一100元父账户下使用新提示词，复用V2登记原始材料，不转移findings、assessment或draw。FRAME已能读取seed材料身份；新run版本记录整个prompt bundle hash。

V3原最终回复不是JSON；一次格式修复后返回complete，但3个前置EvidenceRequests没有claim/issue/draw归属。原文核对另发现：17条引文中16条精确匹配，一条把返回正文中的 `20\(\times\)` 改成 `20x`，仍被拒绝。格式修复只解决输出结构，不能把无归属请求或非原文摘录认作已验证证据。这仍是调查阶段失败记录，没有可报告的自然卡链。

## V3：受限原文复核与历史卡保存停点

`acc012a`已提交受限复核路径：前置EvidenceRequest通过上下文绑定，JSON Schema不变；excerpt mismatch允许恰好一次独立source_recheck，同模型、同预算，仅允许 `read_record` / `request_capability`。原失败任务保持不动，复核再失败则停止。

任务 `arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V3.discover.shared_investigation.source_recheck` 已ACCEPTED，新增15条findings和3条contrary_findings，共18条，严格原文校验通过。旧shared_investigation仍为PAUSED_PROTOCOL，没有被改成成功。Nature目标的3次实际read_record为：

- `tool_25f01d80cb084e86ba4a8d2341d1f44a`
- `tool_e46501ce7ddf4c6bbef0d88c8c40b273`
- `tool_c8419596d204478bb90a9b2294d5e19e`

只读审计记录：隔离工作目录 `work/v3-recheck-audit.json`，本地副本已核对任务ID、3个call ID、18条校验与原失败任务保留。其 `new_model_or_MCP_calls=0` 指只读审计没有额外调用，不表示此前source_recheck免费。该记录对应原文重读这一步，不代表idea审核通过。

随后draw1.next通过，COMPOSE已ACCEPTED并生成7个新claim：`clm_meas_01`至`clm_meas_07`，均version 1。当时save_card因 `claim_evidence_version_mismatch` 暂停；9处引用实际均是不同claim ID之间的背景依据，不是同一claim旧版本证据偷渡。eda3965恢复后卡已正式保存，历史草稿与失败原件保留；这仍不表示discover选择或自然卡链已完成。

[V3_EVIDENCE_REVIEW](V3_EVIDENCE_REVIEW.md)说明了18条exact之外的实质问题：原作者删除像素的IoU公式与固定GT集合定义冲突；模型颠倒了下采样与形态学操作顺序、误记章节；部分“稀疏大对象”标签和域外推断仍混在original事实中。该独立抽查不是专家gold label，也没有注入运行。准确摘录不能保证作者推导、复合claim条件或科研外推正确。

卡保存暂停时的状态快照：V3子账户163调用，人民币2.877053–2.887771，reserved=0。这是V3 child的费用，不是100元开发父账户累计总额，也不是随后恢复的最终费用。

## eda3965恢复结果与当时的真实边界

- **背景依据与定向验证分开。** 不同claim ID之间可以引用背景证据，workflow/report公开binding且 `verification_transferred=false`；同ID旧version仍拒绝。定向EvidenceRecord新增 `target_claim_fingerprint`，覆盖ID/version/text/conditions/kind，不含evidence IDs。empirical resolution包括同card/run历史版本都要求指纹匹配，防止跨卡同名C1混用。
- **请求归属按冻结上下文检查。** pre-card请求只需真实run/task，没有campaign的独立proposal也允许；如填写claim/issue/draw，必须在该任务冻结输入中可见。
- **复核动作绑定实际目标。** source_recheck需其自身read_record的 `result.source_id`、content与 `arguments.record_id` 匹配目标，不能只检查顶层source_ids；实际read_record该字段是[]。

这些改动随eda3965提交并通过255项整合测试。V3恢复（当时启动PID 3080417）复用原frame/shared/recheck/next/compose检查点，没有重付这些已保存步骤，卡登记成功。随后novelty的非JSON正文使用一次结构修复，修复后仍有三个EvidenceRequests的claim/issue/draw目标全null，终态为 `INVALID_OUTPUT_AFTER_REPAIR`，没有accepted novelty。这个协议失败不作为科学否决；原件、旧草稿与evidence均不人工patch。

该novelty停点的V3子账为人民币4.529248–4.539975。它比前述卡保存历史停点晚，但仍不是100元父账户总费用，亦不包含随后两个独立联合probe或L2软件输入阶段的子账。

后续2b8b79a与0f66f56的协议修复已通过离线检查及两模型联合真实probe，但没有重写V3的失败任务或宣称它已获得新颖性通过。`arc-vnext-validation-20260907.explicit_input.develop` 与 `.explicit_input.run` 使用明确标记的软件验证输入，结果见下文。它们不属于自然发现卡，因此即便完成也只能补足相应L2证据，不能替代L3。

## 独立L2输入的实际停点与535357d修复

develop的import、fresh_verification、development、round1 proposer/skeptic已保存，moderator未完成时触发 `PAUSED_BUDGET`。子账花费4.106986–4.107017元，剩余15.892983元，低于下一Pro完整请求15.912元预留。没有assessment；不是科学否决。上界核查与可用性限制见 [BUDGET_ADMISSION_REVIEW](BUDGET_ADMISSION_REVIEW.md)。

独立原文复核发现development原始响应漏了claims键，旧schema静默补[]后保存v2；skeptic仍把背景evidence的旧claim ID当当前目标。另一争点将IoU=.80扩大为边界带近全覆盖，原文不足以支持；NucVerse3D只读取90000/124840字符，缓存尾被误认全文尾。它们都是尚无moderator裁决的失败证据，详见 [L2_EVIDENCE_REVIEW](L2_EVIDENCE_REVIEW.md)。

独立run停于导入。固定轨迹抽查发现连续215次零正文read_record；最近40次是20个metadata-only来源各读两次，未取得新原文。开发者临时在仅该run的下一笔预算INSERT准入处设暂停，允许已开始的 `call_c3532cc771304bff85d163e3aad6cb69` 完整返回、保存、结算后拒绝下一工具请求。进程退出后移除临时限制；账户和授权hash未变，全部调用SETTLED，reserved/unknown均0，完整性/FK检查通过。子账654调用、6.464293–6.464552元。保存原ERROR/IntegrityError原因后，运行标为 `PAUSED_PROTOCOL / metadata_source_empty_read_loop_development_pause`。

暂停审计位于 `.arc-validation/artifacts/maintenance/pause-empty-read-validation-20260907.json` 及 `pause-empty-read-validation-20260907-close.json`。这是开发者根据轨迹实施的控制暂停，不是产品自动检测循环，也没有截断响应、伪造费用或重置预算。

535357d使claims必填；删除复核需旧版本和非空说明；明确的结构化claim/issue引用限制在当前卡与ledger；read_record保留原文总长并区分缓存分页，对无正文来源明确要求补取。没有把自由文本强行解释为ID，没有添加固定调用次数或关键词停机规则。旧付费响应、卡与判断不补回不重写。详见 [CLAIM_AND_SOURCE_FIXES](CLAIM_AND_SOURCE_FIXES.md)。

新渲染自然链 `arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover` 按预登记主题与默认五次上限启动，使用新代码与新bundle，仍属原100元父账本。其历史shared_investigation停点见下节；不能以离线修复证明真实科研链通过。

## Rendering：来源ID复写错误、重复命中误拒与成功恢复

Task `arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover.shared_investigation` 首次停点为 `PAUSED_PROTOCOL / unknown_source_id`，accepted_result=null。停点子账为人民币1.303072–1.303085，66次模型及工具账本调用，reserved=0；不是开发父账户总费用。完整冻结原件、结构修复过程及19条摘录核对见 [RENDERING_EVIDENCE_REVIEW](RENDERING_EVIDENCE_REVIEW.md)。

唯一的来源ID差异位于修复后候选的 `$.result.actual_searches[1].source_ids[5]`：模型写成 `src_d981b8788f84791b2af69a2f07ae529`，本task成功搜索 `tool_a18a8794e6dc476a836949b39cd63b2d` 实际返回 `src_d981b87884f84791b2af69a2f07ae529`，漏写一个4。真实ID已在来源表，属于搜索metadata；不在19条finding的来源或摘录中。18次搜索声明与实际trace逐项核对，仅此一项不同。

19条findings涉及13个来源，摘录均在已保存正文及本task实际返回的正文片段中精确出现。它们在该历史停点尚未登记，科学内容保留；摘录匹配不是全部科学、许可或可行性主张成立。原始生成JSON本身还有尾部/字段类型等结构问题，一次repair后才得到可解析候选；不能将原始生成描述为除ID外已完全合法，也没有再发第二次repair。

已实现的通用修复由Runtime从本task已经完成的search真实trace派生actual_searches，单独保留原始模型声明和执行事实审计；不按字符串相似度猜ID，不改raw、修复后研究字段、预算或一次repair上限。任务书§6执行事实、§7保存响应后本地恢复、§11真实trace验收的依据见 [SEARCH_PROVENANCE_FIX](SEARCH_PROVENANCE_FIX.md)。5e3830c整套290项通过后，首次禁止新增动作的真实恢复仍因duplicate_source_reference暂停，日志 `work/recover-rendering-provenance.log`：actual_searches[5].source_ids实际连续返回两次同一src_48b4ff39da4d46ecb4f9afcbc8cb6c8a，派生日志忠实保留，旧科研引用唯一性检查误拒了执行日志。bac3659仅允许typed执行记录保留真实重复命中，不放松科研引用或来源存在性检查。

`bac3659`的禁止新增模型/工具动作恢复已通过：shared_investigation为 `ACCEPTED`，error=None，19条findings已登记；原始raw及除actual_searches外的研究字段完全不变，repair_count=1，new_model_or_tool_calls=0。恢复窗口父账本保持1157调用、人民币18.981215–18.992283、reserved=0。审计路径相对于 `.arc-validation/artifacts/`：`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover/implementation-fixes/bac3659512f2bae137b8a0241b71c64c17ff3549.json`；normalization审计hash为 `16cd9bf3476c7e3c032d3b24b245708b2fe9c1e63d5847a625d40a8f5be540e4`。该账本快照不包含随后已恢复的自然抽卡新增调用。

上述零调用恢复后，自然抽卡继续至卡保存；追加授权前的预算停点如下。19条摘录登记仍不代表全部科学、许可或可行性主张成立。

在d0d7459时点，L2完整入口、L3自然同卡链、L4同材料对照和最终费用汇总尚未完成。只恢复机械检索记录不能作为科学通过或完成整个discover的依据。

## d0d7459追加前记录：Rendering预算停点与L4启动

Rendering自然run已保存 `card_52bce58017164c2b9594c418eb0cac7b` v1，共10条claims，题目为T-LESS固定场景外观/几何覆盖轴正交归因。frame/shared/archive/next/compose/card_archive均为ACCEPTED；draw1.novelty仍为PENDING，run停为 `PAUSED_BUDGET / budget_not_admitted`，没有accepted novelty，selector未执行。

该阶段子账为140调用、人民币4.209140–4.209176、reserved=0；剩余15.790824低于下一次Pro完整请求15.912预留。这是请求发起前的预算准入暂停，并未花完20元，也不是科研否决。父入口快照为1231调用、人民币21.887283–21.898374、reserved=0、remaining=78.101626；父余额不替代阶段独立上限，未将父账户剩余挪给该阶段。

E2E_RESULT记录L2 discover为PAUSED_BUDGET、L3为not_completed、selected_card=null。L4已按EVAL_PLAN于2026-09-07 08:11:25 UTC启动，顺序为segmentation V3、rendering、固定conflict holdout；该快照只记录启动后的运行中状态，无完整评价结果，不能据此关闭L2/L3/L4；不将它当成追加授权后的最终状态。

真实报告在隔离目录重建的审计为 `work/report-check-bac3659/arc-vnext-validation-20260907.explicit_input.develop/AUDIT_RESULT.json`：7条引用均属于同一run，跨run引用数为0；研究记录hash及PAUSED_BUDGET状态保持不变。因此，本次真实重建只证明所观察报告重建不改变研究状态；跨run链接真实分支未观测，该快照仅有 `tests/test_reports.py` 的 test_cross_run_report_resolves_only_referenced_inherited_evidence 等真实Store离线回归证据。

## 启动SSH退出后的独立进程存活与L4首个技术停点

真实独立进程验证见 `work/ssh-detached-verification.json`。2026-09-07 08:11:25 UTC通过nohup启动PID 3797713，启动SSH正常exit 0（退出码由主线程当时观察，审计文件明确未独立重采）。08:13:11与08:14:06 UTC的新连接均观察到PPID=1、SID=3797713，启动launcher已退出。首个ARC.frame原始请求 `call_82f4d131de9f41b6a5fca6a7dd588846` 与唯一repair `call_d83ed0a8652e4413b50fa5eeb88a6c6a` 均已完整返回并SETTLED，随后direct-Pro.compose的 `call_89dc686a52714b32aa5c72d343ff7f55` 实际进入IN_FLIGHT。它证明独立ARC进程在启动SSH正常退出后继续工作；不证明强制断网、provider流式断流恢复或实际超过24小时。

该首个segmentation V3对照的ARC.frame首次正文为空，唯一repair返回blocked，最终 `PAUSED_EXTERNAL / frozen_material_blocked`，没有accepted frame；ARC子账为人民币1.323994–1.323996。这个记录是技术失败，不是科研否决。08:14:06 UTC冻结快照中direct-Pro仍运行，尚无完整对照或质量评价结果；后续L4结果另行记录。

恢复时间范围：任务书要求取消任意“24小时后不可续跑”的失效规则，并验证旧状态可恢复。test_response_saved_survives_parse_failure_and_old_date与test_response_saved_before_validation_recovers_locally_after_long_pause使用旧日期和重建runtime验证该工程契约；它们不宣称真实等待过24小时，也不把额外等待设为新的验收阻塞。SSH正常退出后的真实存活证据另按上文范围记录。
