# 功能重构与验收

本轮依据用户提供的[功能重构文档](FUNCTIONAL_REDESIGN_REQUEST.md)执行，目标是产生有研究价值的想法并分析可行性。ARC 不执行研究训练实验，也不代写从实验到论文的完整流程。CodeX 只参与本轮开发评估；正式服务中的能力改进需求由用户评估和实现。

截至 2026-09-09（运行记录使用 UTC），四组八个已知语义对照完成目标纠错验收；新主题无科学反馈的 discover 也已按五次上限结束。ARC 把 draw1/2 留为 NEEDS_EVIDENCE，把 draw3/4/5 推荐为 PROMISING，但五张当前均未通过 CodeX 独立科学验收，三张推荐卡构成科学误放。已选择 draw1 v2 作为后续开发辅助修订起点，这不是批准实验，也不能倒算为无辅助抽卡成功。辅助 develop/run 已跑完全流程，但仍有独立检出的错误；后续两个独立 final-correction 分别保存并通过自然卡两项、旧卡四项已知目标的辅助定向验收，不倒算为自主查错或整卡穷尽通过。[A–E两轮已完成](FUNCTIONAL_ABLATION_RESULTS.md)；新审推动局部实改，但两轮E均未通过独立科学核对，r2最终review仍为revise，不能宣称科研质量已提高。具体结果见[验收结果](FUNCTIONAL_VALIDATION_RESULTS.md)。

## 默认工作链与边界

新 discover 使用按需调查 → Pro 连贯构思 → 独立科学审查 → 必要时定向修订与复核。修订仍属于原 draw，不刷新最多五次的抽卡计数；允许提前 STOP、拒绝普通题目和零推荐结果。一次科学循环可以结束为线索或待补证，不能因循环结束就自动推荐。开发中可以显式建立后续修订任务，保留原失败及费用。

discover 结束后显式选卡才进入 develop；随后再显式进入 run 的压力审查。角色职责不展开成九个必经阶段。旧 discover 和 debate 路径只用于恢复既有历史任务；同材料消融中的分步构思使用当前公共科学规则。

工具参数与最终 JSON 各有一次正式任务纠错机会；该额度不限制开发修复。运行身份、计费、版本派生和恢复仍由既有代码管理。实质主张变化只复核受影响的支持关系，等价表达修正须有独立语义审查依据，不能自动继承证明力。

## 逐条任务书映射

下表将实现、已有证据与尚待验证分开；测试名称是对应检查入口，不代表所有新提交已完成整套回归。

| 任务书条目 | 实现与检查入口 | 当前证据及验收边界 |
| --- | --- | --- |
| §1、§5：洞察优先，科学正确与研究价值分开 | `common/scientific_goal.md`、discovery/scientific reviewer；价值校准测试 | v2 错误稿修正后仍可 routine/reject；case5 的价值高估和已见卡校准均保留。不能据此宣称优于 direct Pro |
| §2.1：原题、实质条件持续可见 | `research_context.build_research_context()`、统一 `context()`；原题跨修订/恢复测试 | 输入分别呈现原题、用户 boundaries、FRAME mandate 与提案来源；v2 冲突总体组实际修复偏题。但 draw2 审查仍把候选“不训练探针”写成用户要求，draw3 首稿也有此问题：传递正确不等于模型理解正确 |
| §2.1、§14：L4 输入一致 | `evaluation.py` 明确 original_task，并传 FRAME mandate 至 NEXT_DRAW/COMPOSE 与审核 | 输入传递测试通过；三个旧主题仍是开发回归，不能重新当未见留出 |
| §2.2：查错必须改正文再复核 | `scientific.py`、CONCEIVE/REVISE、ScientificReview/ScientificRevision；科学闭环测试 | v2 四个错误例实际保存修订，四个正确例无目标硬错误误报，仅覆盖这些已知用例。draw1/2 留下未修缺陷；draw3 将审查者的新数学错误实际写入正文并通过复核，证明接线完成仍不等于正确纠错 |
| §2.3：verified 只证明出处定位 | Store 原文定位检查、上下文 `provenance_verification`、科学支持关系审查 | 数字归属对照与旧卡原文核验有真实证据；仍须检查对象、设置与推论，不把摘录匹配当结论正确 |
| §2.4：检索、工作材料、正式引用分开 | `research_context.py` 按当前卡/争点/登记证据选择来源；`reports.py` 将搜索轨迹另列 | 旧 v7 装配为43工作来源、57证据；新自然最终报告22正式来源均有卡片/审核引用，157检索来源中135未进正式引用。引用分层有效不等于科学理解正确；没有域名黑名单或领域猜测过滤 |
| §2.5：按变化复核，检索不可达不解决科学争点 | semantic claim edits、support review scope；调查与审核提示词 | 等价/实质修改与受影响支持关系测试；旧卡补证仍发现新问题并保留 NEEDS_EVIDENCE，没有用访问失败证明贡献新颖 |
| §3：短主干、最多五次、显式后续阶段 | `scientific.discover`、新 develop/run、自然启动器；阶段及恢复测试 | 只有 DeepSeek v4 Flash/Pro，当前 max、Pro 默认核心构思；自然 discover 已完成五个 draw；开发辅助 develop→run 已完成，最终仍有独立查出的错误；后续独立纠正仅通过两项已知目标，默认分工不是已证最优 |
| §4：Markdown 管理认知任务，代码处理契约 | `prompts/manifest.json`、角色/task Markdown、类型化局部 SectionUpdate | 装配、字段诊断和恢复检查；v1 结构失败保留。必要引用/claim/工具契约仍存在，不声称所有元数据已消除 |
| §6：调查形成关系判断，支持按需深读 | investigator、curated excerpt/locator、read_record；`evidence_request_handoff` 按当前候选链交接具体问题 | 新主题四篇冻结全文；draw2 实际 64000 字符连续分页并查近邻。complete 响应的请求已接入后续判断/修订，复核保留初审与修订请求；交接不等于补证完成，已有冻结输入不改 |
| §7：先核心认识，再推最小检验 | discovery CONCEIVE 与当前分步提示词；机制、边界、简洁方法的校准例子 | draw1 探索充分性/可恢复性错位，draw2 探索漂移文本特征，draw3 分析稳定停止事件，但最终概念增量依赖错误公式；draw4 比较评分通道及成本、draw5 比较候选概率与正确性，两者核心成本/统计推论也未通过独立核对。候选与 substantial 自评都不等于已验证洞察 |
| §8：独立重建论证，给具体位置、依据和后果 | scientific reviewer 的 source_read/counterexample 与位置化 findings | v2 四类目标错误均有具体修订；draw1 复核用纯位置反例指出 AUC 结论规则错误。draw3 公式误放、draw4 事实与成本推论漏检、draw5 概率/成本与来源误读获推荐，显示最终语义验收仍失败；不能由 scope_faithful 或 resolved 自报验收 |
| §9：定向修改，可删减；风险附注不算修复 | `apply_scientific_revision`、recheck；无实际改动/错误位置/恢复去重测试 | 已有真实前后版本；draw3 参数真修复与错误公式继承并存，缺少对审查建议本身的可靠复核。旧卡首次修好六处等式，targeted仍误放；最终独立纠正已保存四项算术/推论实改并通过定向验收，不升级为整卡穷尽通过 |
| §10：方案展开只服务决定性检验和可行性 | developer 提示词、新 develop 后独立审查 | 真实develop v3已完成：反馈引导下数值/定义/方案改善，自主初审零finding却漏四项核心推论及资源错误；run进一步修订。阶段完成和契约检查不证明方案科学成立 |
| §11：压力审查与裁决是职责，不是必经长辩论 | 新 run 调 `pressure.science`，按被审卡版本写最终判断 | 旧卡初轮NEEDS_EVIDENCE；自然run v4已COMPLETED/PROMISING，复核仍漏双减t*及不显著归因错误；独立final-correction v2只通过上述两项已知反馈目标 |
| §12：首页先展示洞察与风险，零推荐也解释原因 | 生效的 reports.py 与报告模板；当前版本判断、引用隔离、零推荐报告测试 | 已修未推荐理由、COST_REPORT 状态及 LEAD_ONLY 洞察前置。最终自然报告22正式来源、157检索附录；f9aad60 已按5候选/9版本分类并只读重渲染，3主报告/2线索正确；9份详情和修复前报告保留，22来源集合与源卡/账本不变 |
| §13：校准区分成立、平凡、简洁而重要及改题 | `selection_examples.md` 与价值校准测试 | value-v3 对已见正确交互卡 routine/reject、无硬错误；不覆盖初轮价值高估，不当泛化分数 |
| §14 第一层：正确/错误成对、真实前后对照 | v1/v2 fixtures、只读 controls 导出器及人工核对 | v2 8/8 为 4 错修好＋4 对不误报目标错误；不是 8 个有价值 idea。v1 失败完整保留 |
| §14 第二层：冻结材料 A–E、交换顺序、独立费用 | `functional_evaluation.py`、ablation 导出器；候选/初审复用与 phase 测试 | A Pro 连贯，B Pro 当前分步，C Flash 当前分步，ABC 统一旧审；D 复用 A 卡新审，E 复用 A 卡及 D 初审修订。r1全条件及双序评价已完成，18实际调用；A/D同稿、E复用D初审，局部实改但E仍有硬错误。r2也已完成，22实际调用含纠错与显式恢复；两轮材料/current38/legacy35文本分别相等，A=D和E复用初审确认；偏好不一致且E仍有硬错误，未证明质量提高；seed只匿名顺序 |
| §14 最后：新主题自然全流程 | `start_natural_validation.py` 分步建立新 campaign，不把 material_only 当生成结果 | discover 已 COMPLETED / draw_limit_reached：五候选、九历史版本，2 LEAD_ONLY＋3 PROMISING；独立验收五张均未过。draw1 v2仅作为开发辅助修订起点；develop/run已完成但仍误放，新独立final-correction仅两项已知目标通过；旧三个主题与旧v7不称未见主题 |
| §15：公开研究仅作设计借鉴 | 原任务书参考资料与本次实现/结果分开记录 | SciMON、CoVe 等不能代替 DeepSeek/ARC 实测，更不能作为当前质量提升证明 |

## 本轮运行期修复与软件验证范围

已确认的运行期修复包括：补证复核聚焦受影响的支持关系，同时允许发现相关新缺陷（`99bc219`、`f70b937`）；明确“提交当前候选”与“停止后续抽卡”的区别，并在 STOP 携带候选的结构错误中给具体纠正诊断（`1f2e52e`、`e7810ea`）；存档比较允许已核验的额外卡，同时保留必需覆盖要求，并在消耗一次 JSON 纠错前反馈覆盖错误（`58afeac`、`5b2b9de`）。这些修改修复契约表达与诊断，不自动批准任何科学候选，也不抹去原失败。

随后补齐的四项修复及验证边界如下。下面的本地模拟检查没有调用付费模型，不能当作真实科研效果实验。

| 提交 | 修复内容 | 已验证范围 |
| --- | --- | --- |
| `ca6b222` | evaluator 缺候选、重复或未知候选 ID，在接受前进入已有一次 JSON 纠正，返回期望与实际覆盖 | `test_evaluator_output_repair.py` 检查覆盖纠正、无候选时允许无偏好，以及不得刷新已用额度；不是强制选择赢家，这项本地测试本身不代表真实双序评价；r1实结果另见消融报告 |
| `913b989` | CONCEIVE 可为本次返回候选中新声明的 claim 提出补证请求 | `test_conception_target_resume.py` 模拟旧协议暂停，修复后复用同一原始响应，不增加模型请求；真实 draw3 也已复用缓存接受 v1，仅证明结构恢复 |
| `72e09e5` | 补证请求的 claim/issue/draw 目标绑定错误进入同一次 JSON 纠正诊断 | `test_evidence_target_repair.py` 检查三类未知目标的 expected/supplied 诊断及额度已用后继续暂停；相关落地回归记录为 114 passed，不代表完整软件或科学验收 |
| `eb9e0bf` | complete 响应中的核验请求沿当前候选链传递，保留实际任务来源与 claim 对应并按来源任务/request_local_id 去重 | 相关六文件 70 项通过，随后新增 support 分支用例后独立交接文件 7 项通过。检查覆盖 conception/development→review、初审/修订→recheck、已有 support 分支及冻结输入恢复；请求存在既不证明已完成，也不证明仍未完成 |

行为指导写在科学目标 Markdown：接收角色对照已有证据和前序核验判断是否需要补读，不增加自动必经调查阶段，不重复购买已有充分核验。新接线不回写历史任务的冻结输入。真实 draw3.science.review 已冻结输入含 `er1_es_cot_full_text` 完整问题及 claim/source/draw 对应，来源为原 draw3.conception，原始 boundaries 正确；这证明运行时交接接通。后续显式 retry 的初审确实读到 ES-CoT 剩余正文并修正参数，但该次实际补读也不能证明所有请求或科学问题都已解决。

真实 draw3 随后暴露了另一条接入链缺陷：两份 read_paper 原件成功返回，但因 title 为空未登记，旧来源缓存耗尽后发生跨轮空读。修复原文登记并给出明确缓存耗尽错误后，同一任务仍持续空读；CodeX 在两次已保存且无活跃预算调用的安全点停止任务，再用原 raw 零 API 登记两份独立表示，显式建立 `review.protocol_retry1`。这属于开发运维恢复，不是 ARC 已完成科学自纠；原 trace、费用、卡片及五次 draw 上限均不重置。`2074cce` 仅压缩重试工作视图中的重复空读，不把失败当证据，也不向任务注入科学答案；20 项相关测试通过。此后 retry 初审、修订及复核已经结束：原文参数修好，数学错误却被最终推荐；接入恢复与科学验收须分别报告。完整事故证据与费用归因边界见[验收结果](FUNCTIONAL_VALIDATION_RESULTS.md)。

最终完整软件验证为 **55a134c：707 passed，0 failed/error/skipped**，于2026-09-08 21:08:02 UTC完成，含sdist→wheel、仓库外隔离安装、38份提示词/18任务/3配置、4CLI与依赖检查。原件`work/software-validation-20260908T210458748151Z/SOFTWARE_VALIDATION.json`，唯一包组与JSON已同步Windows。

r2暴露后分开修复：11d95ae把selector前提矛盾纳入既有JSON诊断；909f235准确恢复已接受但应用失败的ablation任务；05cf26e令未完成CLI非零退出。相关64项通过；首次命令错误的0tests日志保留。05cf全量706通过/1失败来自旧错误字符串断言；55a134c改为结构化type/loc/supplied检查，**未删除测试**，9相关与707全套通过。05失败、31fc58c/694及更早各软件快照完整保留，来源见[验收结果](FUNCTIONAL_VALIDATION_RESULTS.md)。

两轮材料与提示词保持，但r2恢复窗口使用了新协议修复；跨轮不能称执行代码完全一致。所有失败、费用及冻结任务身份保留，后补修复不回填为早期科学能力。

本轮科学功能验收仍有实质缺口：八个已知对照的成功没有迁移成可靠的自然判断。五个无辅助候选均未通过独立验收，其中三张被 ARC 推荐。`work/NATURAL_SCIENCE_AUDIT.md` 保留自主查错、真实修订、误放及 CodeX 自我更正；独立反馈没有输入已冻结的 discover。显式 `development_assisted` 的develop/run及两个final-correction结果已单列；最后六项已知目标纠正通过，不能覆盖原五卡失败或改写为自主成功。

[MASTER_STATUS](MASTER_STATUS.md)与[DELIVERY](DELIVERY.md)已分开当前入口与历史快照；L4和旧自然报告保持原记录。A–E两轮及双序评价、独立核对已完成，无科研质量提升结论。费用沿用既有父/子账本；本文不固定正在变化的余额或最终总额。

## 本轮收尾核对

- 已按实际call_id完成两轮模型/effort、起止、纠错与失败成本审计：r1 18、r2 22条全SETTLED，E完整链分别3.132334与3.487622元上界，无重买D初审。
- 已逐字比较两轮材料与各自current/legacy快照，并核各任务实际加载文本、A=D及E初审复用；没有额外哈希校验。
- 已完成两轮科学/双序独立核对，保留无偏好、位置敏感结果及错误。真实局部修复不等于可靠科学审核，不以自动偏好宣布质量提高。
- 最终文档与Windows报告同步，当前软件55a134c/707。主线程仍将补最终实际清理记录；付费原件、验证日志及五个自动审批拒绝的Windows路径保留，不写成已删除。
