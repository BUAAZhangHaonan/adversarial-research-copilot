# Discover First：轻量发现主线

日期：2026-09-09。以本轮 `ARC_Discover_First_CodeX_Execution_2026-09-09.md` 及配套 Markdown 为需求依据。默认路径、提示词、存储、报告与人工交接已落地。软件记录见 `DISCOVER_FIRST_SOFTWARE_VALIDATION.json`，实际产物与限制分别记录，软件通过不代表科研质量通过。

## 目标与顺序

共享领域调查 → 单个短灵感 → 价值初筛 → 仅对入围者定向预研 → 人选择。

投入重点是理解文献、产生不同认识和核查关键前提。普通题目早停，有启发但尚不成熟的题目允许保留；不把每个想法变成完整实验协议，不以多轮一致认证科学正确性。

## 实际接线

| 要求 | 当前连接与行为 |
| --- | --- |
| 替换默认 discover | `cli.new_run` 为新 discover 设置 `discover_first`；`WorkflowEngine.discover` 分派至 `discovery_workflow.discover`。新路径直接持久化轻量对象，不调用 `CardDraft` 或 `review_and_revise` |
| 共享领域理解 | 首次 `scout.SURVEY` 生成 `FieldBrief`，包含 overview、research_lines、openings、source_notes、search_limits。`research_context.build_discovery_context` 在每项语义任务带入原题、明确限制和共享资料 |
| 短灵感先落地 | `ideator.SKETCH` 输出一个 `IdeaSeed` 或 skip/stop；完成后立即保存稳定 idea ID 并更新报告，不等待完整五次抽卡 |
| 先筛价值再花钱 | `editor.TRIAGE` 不开放外部工具。investigate 才调用 CHECK；park/drop 当次终止候选，不追加科学修订、付费报告员或裁判 |
| 有限候选预研 | `scout.CHECK` 直接返回 `CandidateCheck(note, field_updates)`。检查近邻、关键背景和实施通路，允许明确限制和未知；实际工具 trace 用于确认取得相关检索/读取，不靠模型声明“已查新” |
| 材料复用 | CHECK 的 SourceNote 更新并入当前 FieldBrief，之后任务可见；保留来源身份及阅读层级。SKETCH 的具体 next_search 最多触发一次共享补查，checkpoint 保留跨暂停状态 |
| 紧凑历史 | 同主题传递 previous_directions；本地 FTS 召回少量历史卡和轻量 idea 给编辑比较。无检索命中不代表不存在相似工作，词面相似不自动否决 |
| 独立轻量存储 | `discovery_models.py` 提供 FieldBrief/IdeaSeed/TriageResult/IdeaNote；`Store.save/get/list_discovery_ideas` 使用专用轻量表，关联原 run、draw、主题、简报版本和时间，不构造逐句 claims 账本 |
| 次数和预算恢复 | 仍最多五次 SKETCH；通过 `claim_draw` 与稳定任务键记机会，skip/stop计次。重放接受结果和同一任务纠正不新增draw；调查及所有候选共用当前阶段账本 |
| 人工后续入口 | `develop --idea` / `run --idea` 传入初始seed、最新预研、原题、明确边界和共享调查；分别调用 `scout.DEVELOP` / `scout.PRESSURE`，结果保存在当前run的 `prestudy_note`，不自动串联 |
| 报告直接生成 | `render_run` 分派至 `render_discovery_run`，直接渲染 Markdown；支持 pending、park、drop、checked 与未提交seed，先显示想法和价值再给来源与运行记录 |
| 模型配置解耦 | `Settings` 解析 research_model/roles→models 别名；`model_adapters.py` 封装当前供应商参数与支持能力；runtime 调用适配层，工作流与科研Markdown无型号判断 |
| 生效提示词 | manifest 合并四个发现任务和两个后续任务。新任务只加载 `discover/` 与对应 `prestudy/` Markdown；未叠加旧完整科学审查政策。打包资源显式包含两个目录 |

旧完整卡/问题入口和历史开发命令继续显式可用，不属于默认轻量发现链。历史失败、旧判断、原始来源和费用不会因本轮更换产品定位被修改为成功。

## 工作对象与用户状态

`FieldBrief → IdeaSeed → TriageResult → IdeaNote`。系统生成稳定 ID、run/draw 关联和记录时间；模型负责研究内容。

| 字段/状态 | 含义 |
| --- | --- |
| `pending` | 已保存短灵感，初筛或定向预研尚未完成；不是推荐 |
| `park` | 编辑认为有启发但不宜立即展开，保留给人；尚未做CHECK |
| `drop` | 初筛有具体理由放下；不为挽救想法追加完整方案 |
| `checked` | 已取得预研对象；实际建议仍需看note.decision |
| `discuss` / `lead` / `drop` | 分别为值得讨论、有条件线索、本次放下；不表示科学认证 |
| `PAUSED_*` / `ERROR` / `COMPLETED` | 软件执行状态，与上述研究建议独立 |

若没有观察到本候选相关的有效检索/读取，预研会保留访问限制，不能以 discuss 表示已经完成必要查证。尚未执行实验本身不构成降级理由。来源阅读层级来自实际材料边界；明确引用错误应在短卡中纠正或停止推荐，新假设可以保持未证实。

后续阶段收到的旧 note 另存 `INPUT_IDEA.json`；当前报告仅使用当前 `prestudy_note` 的判断。旧卡的 discuss 不能代替尚未完成的 develop/run。

## 提示词与报告

发现任务注册：`scout.SURVEY`、`ideator.SKETCH`、`editor.TRIAGE`、`scout.CHECK`。后续注册：`scout.DEVELOP`、`scout.PRESSURE`，仍是三个职责，不是新增六名Agent。

`discover/policy.md` 定义预研目标；researcher/ideator/editor分别规定材料、构思和初筛职责；calibration含平凡但完整、不成熟但有意义、简洁方法等对照。`prestudy/develop_scope.md` 与 `pressure_scope.md` 独立装配，未附着在相互冲突的旧审查指令之后。格式修正和工具说明仍由已登记Markdown提供。

报告路径为 `DATA_DIR/reports/RUN_ID/`：

- `REPORT.md`：候选摘要、去留、待预研及运行停止原因。
- `ideas/IDEA_ID.md`：当前短灵感或预研卡；未知资源不补造数值。
- `FIELD_BRIEF.md`：共享调查及关键来源阅读范围。
- `SEARCH_SOURCES.md`：检索命中审计，不自动纳入正式引用。
- `PROMPT_TRACE_INDEX.md`、`accepted/`：已保存任务与原始材料链接。
- `COST_REPORT.md`、`DISCOVERY_USAGE.json`：费用、语义任务、实际模型请求、工具动作、token及首个seed/note时间；未发送预留不计实际请求，工具账目不计模型请求。

报告不重新调用模型、不改变存储判断；关联来源仅来自当前候选及资料笔记，来源可定位不代表语义正确。完整来源、失败响应及费用继续私有保存。

## 模型配置边界

现有配置默认 `research_model: deepseek-v4-pro`；scout/ideator/editor均采用该别名，用户可在 roles 明确覆盖。型号、供应商参数、token上限与计费留在配置/适配层。

新增别名需要提供实际 provider/model、端点、凭据环境变量、操作能力和匹配的价格/上限快照。`openai_compatible` 要求显式 base_url 与 api_key_env；不继承 DeepSeek 的 thinking 或私有 reasoning_content。支持范围是已实现的 Chat Completions JSON、工具、streaming usage 协议；其他协议或计费方式需要单独适配。

`pricing_path` 指向经过核对的价格配置。不能只写一个新型号名字便假定其价格、工具或输出能力与已有型号相同。兼容性以模拟配置检查，不购买或比较新模型。未知别名、缺少凭据、未支持操作和价格上限不一致均明确报错。

当前 DeepSeek 保留 max 与384000完整输出上限。科研提示词不包含型号绑定，默认不会自动降低核心步骤模型。单次预算不足时暂停下一请求，不截断已开始回复。

## 验证记录

以下表格保留首轮软件检查与暂停现场。用户后来授权完成这两个任务；最新进展、恢复说明和最终费用见 [续跑记录](DISCOVER_FIRST_CONTINUATION.md)。

| 检查 | 当前记录 |
| --- | --- |
| 默认轻量流、共享材料、早筛不调用CHECK、额度恢复 | 集成覆盖seed先存、park/drop不查、资料合并、STOP/刷新恢复和稳定draw |
| --idea 人工交接与当前阶段状态 | 离线通过显式选择、输入资料继承与当前阶段独立判断；没有付费运行后续阶段 |
| 模型别名、供应商边界及Markdown打包资源 | 模拟别名/适配边界通过；最终wheel的6项任务及修复Markdown可渲染，CLI暴露--idea |
| 必要整体回归与安装 | 整体779项通过；后续来源37项、JSON模板88项、适配/运行时109项、来源诊断38项相关回归通过；安装检查通过 |
| 开发例1：多模态模型在真实任务中何时需要主动获取额外信息 | 已运行；1条待预研seed，CHECK格式纠正遇HTTP400后暂停；已结算3.474208元，未知预留15.912元 |
| 开发例2：具身智能在环境变化后如何使用和更新既有经验 | 已运行；SURVEY来源ID一次纠正仍无效，尚未进入SKETCH；已结算1.516984元 |
| 本轮实际费用与原父账本剩余额度 | 本轮已结算上界4.991192元，未知预留15.912元；当前最大费用占用20.903192元，父账本剩余84.632470元 |

首轮采用最多两个discover、各20元、累计40元及一次调整的开发限制。用户随后明确授权使用现有不足100元余额完成这两个暂停任务，该授权替代首轮停止限制。仍不清零历史花费，不新增样例、模型/流程对照或付费develop/run。

人工阅读关心：是否有具体认识，是否有实质近邻区别，背景事实是否有据，多张候选是否重复，以及阅读是否省力。CodeX可做开发自查，不能替用户宣布科研品味提高；零推荐也如实交付。不完整、平凡、资料不足、执行故障分别描述，不统一包装为科学成功或软件失败。

## 续跑最终状态

两个原暂停样例均COMPLETED，各5次构思与5份预研记录，合计8 discuss、1 lead、1 drop，无pending。续跑新增20.371510元；两例累计25.362702元，原UNKNOWN预留15.912元另计。原HTTP400和SURVEY来源失败保留；缓存无进展修复124项及报告/提示词38项相关回归通过。实际恢复和科研阅读限制见[续跑记录](DISCOVER_FIRST_CONTINUATION.md)。未运行新的模型对照、研究实验或付费后续阶段。

## 历史记录

[上一轮功能验收](FUNCTIONAL_VALIDATION_RESULTS.md)、[A–E历史结果](FUNCTIONAL_ABLATION_RESULTS.md)、[上一轮收尾](FINAL_CLOSEOUT.md) 保留原始结论与费用口径。本轮不重新运行这些付费比较，不将旧科学质量失败重命名成新预研通过。
