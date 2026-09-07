# 真实验收记录

本文件按层级分开工程契约、真实接口、自然研究卡贯穿和自动质量对照。自动判断不是人类认可，PROMISING 不是实验成功。

截至2026-09-07本次更新：代码 `535357d` 的283项工程测试与独立wheel通过；较早0f66f56的Flash/Pro JSON加原生工具联合真实probe均COMPLETED。V3自然卡已保存，但novelty在一次结构修复后仍为 `INVALID_OUTPUT_AFTER_REPAIR`，没有accepted novelty或科研裁决。明确标记的软件输入develop停于预算准入，独立run因反复读取空正文而在新请求边界由开发者暂停。新渲染主题自然链正在验证535357d的通用数据契约修复；L2未全部完成，L3未完成，L4未执行。

## L1：工程与安装包

- 最新代码快照：`535357d`，283 tests passed / 52.08s，日志 `work/tests-claim-source.log`。该HEAD经git archive构建wheel/sdist并独立安装，从 `/tmp` 验证CLI和包资源；日志 `work/wheel-build-535357d.log`、`work/wheel-install-535357d.log`、`work/wheel-help-535357d.log`。Windows此前快照282 tests / 427.42s不作为最终283项的记录。
- 历史快照：`0f66f56`，263 tests passed / 48.55s，远端日志 `work/tests-json-tools.log`。该HEAD独立wheel验证通过，日志为 `work/wheel-build-0f66f56.log`、`work/wheel-install-0f66f56.log`、`work/wheel-help-0f66f56.log`。源码归档构建后在独立 `.venv-wheel` 安装，从 `/tmp` 检查CLI、0.2.0版本、prompt/报告/配置资源，避免仓库cwd掩盖漏打包。
- `2b8b79a` 固定comparison.boundaries与shuffle_seed，并追加公共请求归属说明；对应258 tests / 46.23s，日志 `work/tests-evaluation-ownership.log`。冻结相同材料和匿名顺序是工程能力，此时并未运行L4质量对照。
- 历史快照 `eda3965`：255 tests / 47.29s，日志 `work/tests-claim-bindings.log`，独立wheel验证通过。它修复背景证据绑定与目标指纹，后续V3卡保存恢复成功。
- 历史快照 `acc012a`：238 tests passed / 43.04s。
- 历史快照 `a8ddc5a`：220 tests passed / 42.42s，并完成独立 wheel 验证。
- 历史快照 `b7b3df9`：211 passed / 41.90s（g203，Python 3.13.5）。该次从受控源码归档构建 wheel，在独立 `.venv-wheel` 安装，工作目录 `/tmp`；`arc --help`、0.2.0 版本一致性、登记 prompt loader 及报告资源加载通过；OpenAI 2.54.0、MCP 2.1.1。原基线87项通过同样仅是历史背景。
- 核心提交：66d998f；快照/继承/包资源：c09e0b9；真实本地读取与原文缓存修复：2f76f4c。修复后的完整测试日志：`work/final-tests.log`。
- 离线覆盖 B01–B18 的证据映射见 IMPLEMENTATION_AUDIT。模拟/合成 fixture 不冒充真实研究证据。

## L2：已完成的接口与恢复部分，三入口尚未完成

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

以上为V2调查过程中的历史修复。最新停点及V3已观察到的失败见下文；目前没有完成自然卡三阶段链，也没有完成L4，不能将这些接口成功写成L2三入口或L3/L4通过。

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

## eda3965恢复结果与当前真实边界

- **背景依据与定向验证分开。** 不同claim ID之间可以引用背景证据，workflow/report公开binding且 `verification_transferred=false`；同ID旧version仍拒绝。定向EvidenceRecord新增 `target_claim_fingerprint`，覆盖ID/version/text/conditions/kind，不含evidence IDs。empirical resolution包括同card/run历史版本都要求指纹匹配，防止跨卡同名C1混用。
- **请求归属按冻结上下文检查。** pre-card请求只需真实run/task，没有campaign的独立proposal也允许；如填写claim/issue/draw，必须在该任务冻结输入中可见。
- **复核动作绑定实际目标。** source_recheck需其自身read_record的 `result.source_id`、content与 `arguments.record_id` 匹配目标，不能只检查顶层source_ids；实际read_record该字段是[]。

这些改动随eda3965提交并通过255项整合测试。V3恢复（当时启动PID 3080417）复用原frame/shared/recheck/next/compose检查点，没有重付这些已保存步骤，卡登记成功。随后novelty的非JSON正文使用一次结构修复，修复后仍有三个EvidenceRequests的claim/issue/draw目标全null，终态为 `INVALID_OUTPUT_AFTER_REPAIR`，没有accepted novelty。这个协议失败不作为科学否决；原件、旧草稿与evidence均不人工patch。

该novelty停点的V3子账为人民币4.529248–4.539975。它比前述卡保存历史停点晚，但仍不是100元父账户总费用，亦不包含随后两个独立联合probe或L2软件输入阶段的子账。

后续2b8b79a与0f66f56的协议修复已通过离线检查及两模型联合真实probe，但没有重写V3的失败任务或宣称它已获得新颖性通过。`arc-vnext-validation-20260907.explicit_input.develop` 与 `.explicit_input.run` 使用明确标记的软件验证输入，结果见下文。它们不属于自然发现卡，因此即便完成也只能补足相应L2证据，不能替代L3。

## 独立L2输入的实际停点与535357d修复

develop的import、fresh_verification、development、round1 proposer/skeptic已保存，moderator未完成时触发 `PAUSED_BUDGET`。子账花费4.106986–4.107017元，剩余15.892983元，低于下一Pro完整请求15.912元预留。没有assessment；不是科学否决。上界核查与可用性限制见 [BUDGET_ADMISSION_REVIEW](BUDGET_ADMISSION_REVIEW.md)。

人工复核发现development原始响应漏了claims键，旧schema静默补[]后保存v2；skeptic仍把背景evidence的旧claim ID当当前目标。另一争点将IoU=.80扩大为边界带近全覆盖，原文不足以支持；NucVerse3D只读取90000/124840字符，缓存尾被误认全文尾。它们都是尚无moderator裁决的失败证据，详见 [L2_EVIDENCE_REVIEW](L2_EVIDENCE_REVIEW.md)。

独立run停于导入。固定轨迹抽查发现连续215次零正文read_record；最近40次是20个metadata-only来源各读两次，未取得新原文。开发者临时在仅该run的下一笔预算INSERT准入处设暂停，允许已开始的 `call_c3532cc771304bff85d163e3aad6cb69` 完整返回、保存、结算后拒绝下一工具请求。进程退出后移除临时限制；账户和授权hash未变，全部调用SETTLED，reserved/unknown均0，完整性/FK检查通过。子账654调用、6.464293–6.464552元。保存原ERROR/IntegrityError原因后，运行标为 `PAUSED_PROTOCOL / metadata_source_empty_read_loop_development_pause`。

暂停审计位于 `.arc-validation/artifacts/maintenance/pause-empty-read-validation-20260907.json` 及 `pause-empty-read-validation-20260907-close.json`。这是开发者根据轨迹实施的控制暂停，不是产品自动检测循环，也没有截断响应、伪造费用或重置预算。

535357d使claims必填；删除复核需旧版本和非空说明；明确的结构化claim/issue引用限制在当前卡与ledger；read_record保留原文总长并区分缓存分页，对无正文来源明确要求补取。没有把自由文本强行解释为ID，没有添加固定调用次数或关键词停机规则。旧付费响应、卡与判断不补回不重写。详见 [CLAIM_AND_SOURCE_FIXES](CLAIM_AND_SOURCE_FIXES.md)。

新渲染自然链 `arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover` 按预登记主题与默认五次上限启动，使用新代码与新bundle，仍属原100元父账本。目前剩余验收为L2完整入口、L3自然同卡链、L4冻结同材料对照与人工复核，以及最终费用汇总；不能以离线修复证明真实科研链通过。
