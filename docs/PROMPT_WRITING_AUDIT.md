# ARC 提示词逐文件审阅

基线：`master@676e76dcd44c626ee70c894a6a06da7e4bffd193`，2026-09-12。共审阅 `prompts/` 下 58 份 Markdown，并核对 manifest、实际 writer.POLISH 与报告渲染路径。目录登记不等于默认运行；以下分别标出当前主链、显式完整卡路径和技术模板。

本表保留用户上传文件中的逐文件审阅，以该基线为对照；其中关于外部文献和此前读取方式的说明属于所提供审阅材料，不表示本轮重新检索或核验。本轮另在 g203 核对真实装配、模板与改动：基线 58 份 Markdown 中 18 份修改、40 份保留，新增一份短共同规范；实际验证见 [实施记录](writing_review/PROMPT_IMPLEMENTATION.md)。旧上传报告用于识别历史写作问题，不代表当前实现仍只有旧 reporter。

## discover

| 文件 | 当前用途 | 观察 | 处理 |
|---|---|---|---|
| [policy.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/policy.md) | 当前研究主链共用 | “不认证”“不构成失败”等职责限制有必要，但与正文语言混写；仅一句“中文简短连贯”不足以示范。 | 替换；研究边界保留，表达交给共同规范。 |
| [researcher.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/researcher.md) | SURVEY / CHECK | 已有来源更新和 current_understanding 接线正确；长字段容易重复，CHECK 容易沿反例、最小验证写成评审意见。 | 替换；保留字段交接与短核对，将 reason、feasibility、risk 分工；不新增科学验证。 |
| [ideator.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/ideator.md) | SKETCH | 已有创意导向；“实质后果”“机制”等抽象词偏多，长篇反向禁令不能示范短灵感。 | 替换；用具体读者目标组织输出，保持一次一张与原计数语义。 |
| [editor.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/editor.md) | TRIAGE | 最新代码已提供本轮与跨运行当前认识；一至两个问题是好设计，但容易泛化为新颖性/可行性审查清单。 | 替换；给具体异议写法，保持 candidate_relation 和去留规则。 |
| [calibration.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/calibration.md) | SKETCH / TRIAGE | 价值校准已覆盖平凡、简洁与新条件；主要教判断，较少展示成稿语言。 | 替换；保留原类型区别，增加自然短判断与必要未知的示范。 |
| [invoke.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/invoke.md) | 当前六项研究任务 | 内部 ID、JSON 与研究解释在一个模板中；应防止模型把协议提醒写入正文。 | 替换；变量、ID 和 schema 完整保留，注明自然语言字段的职责。 |
| [repair.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/repair.md) | 研究任务输出纠正 | 精确来源、阅读层级和原判断保护属于必要控制，不是读者要看的限制声明。 | 原文保留；不把该模板加载进 writer。纠正诊断只在该任务上下文使用。 |
| [writer.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/writer.md) | 实际 writer.POLISH 系统提示词 | 要求摘要 200–350、总览 500–800、每卡 500–800，摘要固定两段，每卡 3–5 文献，整套最多一个公式；内容保护重复出现。 | 重点替换；取消最低配额与机械段落/公式规则，保留信息真实性、当前版本、关键条件和现有上限。 |
| [writer_invoke.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/writer_invoke.md) | writer.POLISH 任务模板 | 与系统提示词重复“不表示已解决”“未知保留”；可简化，协议 complete 不变。 | 替换；只说明当前任务、数据、JSON 与状态归属。 |
| [writer_repair.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/writer_repair.md) | writer.POLISH 纠正 | 仅列格式、覆盖、引用和状态，未充分说明实际会触发的长度诊断；容易只加空行。 | 替换；明确先去重再组织，保留事实条件，不启动研究。 |
| [polished_overview.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/polished_overview.md) | 实际 REPORT.md | 阶段摘要和研究总览各占一节；单卡也列“候选与原始判断”；结尾自述润色不是验证。 | 替换；摘要先行，总览只补背景，候选按数量显示；删除编辑自我说明，保留运行状态与记录链接。 |
| [polished_idea.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/polished_idea.md) | 实际润色后单卡页 | 状态后再次强调人工决定，重复原研究标题和“只整理表达”声明。 | 替换；短状态加正文，保留真实来源阅读层级，旧标题与过程留在技术记录。 |
| [overview.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/overview.md) | 确定性总览／TECHNICAL_REPORT.md | 当前认识、reason、风险和线索说明可能重复；共享概览带长免责声明。 | 替换；简化排列与标签，仍保留调查、成本、暂停及后续动作。 |
| [idea_note.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/idea_note.md) | 确定性逐卡／*.technical.md | 当前认识后重新展开初始灵感、初始动机、修改经过、风险与限制；容易混合新旧观点。 | 替换；当前内容先讲，历史与材料过程移到末尾独立章节，不删除原记录。 |
| [pending.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/pending.md) | 尚未完成预研的逐卡页 | “不是推荐”等重复，多个标签把短灵感切碎。 | 替换；status_text 保留真实未完成状态，正文先说明想法，再列具体缺口。 |
| [field_brief.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/field_brief.md) | FIELD_BRIEF.md | 每条材料把发现、相关性、访问层级挤进一句，研究关系容易退成论文列表。 | 替换模板排布；source_notes 数据不动，重要限制仍可定位。 |
| [search_sources.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/discover/search_sources.md) | SEARCH_SOURCES.md | 完整检索命中审计，声明其不是证据，适合此页用途。 | 保留；不得再把整个列表复制到读者首页。 |

## prestudy

| 文件 | 当前用途 | 观察 | 处理 |
|---|---|---|---|
| [develop_scope.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/prestudy/develop_scope.md) | scout.DEVELOP | 已有预研边界正确；需避免将“进入路径”扩成全部开工条件。 | 替换为相同职责的自然表述，不扩大阶段任务。 |
| [pressure_scope.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/prestudy/pressure_scope.md) | scout.PRESSURE | 区分错误、缺证、研究未知合理；“认证/结束不等于通过”应是内部语义，不反复对人表态。 | 替换；输出具体异议和后果，保持不运行实验。 |
| [output.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/prestudy/output.md) | DEVELOP / PRESSURE 共用 | 最新认识回写、field_revision、decision 都需要保留；缺少各语言字段职责。 | 替换；明确各字段分工，保留全部数据通路。 |

## common

| 文件 | 当前用途 | 观察 | 处理 |
|---|---|---|---|
| [evidence_policy.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/common/evidence_policy.md) | 完整卡／历史路径 | 列举支持条件、来源定位、未证明范围；用作证据控制有效，直接附给轻量 writer 会重复审查腔。 | 保留原职责；不加入新发现或 writer 系统；不把所有核对项变正文。 |
| [output_protocol.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/common/output_protocol.md) | 完整卡／历史协议 | 长篇 Envelope、标识、请求绑定和恢复约束属于机器协议。 | 保持现有协议；与面向人类的写作规范分开，不为口语化改 schema。 |
| [research_policy.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/common/research_policy.md) | 完整卡／历史共用 | 研究范围与拼接限制不是当前报告的直接模板。 | 保留；本轮不再改选题门槛。 |
| [resource_policy.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/common/resource_policy.md) | 完整卡资源说明 | 详细 GPU-hours、工作量与未测依据适合方案记录，不适合反复进入摘要。 | 保留原资源语义；新预研继续用粗估，writer 只呈现影响判断的部分。 |
| [scientific_goal.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/common/scientific_goal.md) | 完整卡／历史共用 | 核心目标和交接要求合理，不是最新默认 discover 的写作入口。 | 保留；不误把修改它当作已改变 writer。 |
| [selection_examples.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/common/selection_examples.md) | 完整卡判断校准 | 用例教科学正确性和研究价值；不是自然写作范例。 | 保留；新写作例子放在轻量共用文件或当前 calibration，禁止恢复旧严格链。 |

## roles

| 文件 | 当前用途 | 观察 | 处理 |
|---|---|---|---|
| [developer.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/developer.md) | 显式完整卡／历史展开 | 含复杂 claim/version/IMPORT 约束和实验展开要求。 | 保留技术逻辑；默认轻量展开使用 prestudy；不做整篇简写而损坏协议。 |
| [discovery.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/discovery.md) | 完整卡 CONCEIVE / REVISE | 要求完整卡和最小完整检验，已不是当前默认 SKETCH。 | 保留历史／显式用途，不启用作为文字修复。 |
| [discovery_staged.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/discovery_staged.md) | 旧 FRAME / NEXT_DRAW / COMPOSE | 分步构思和固定结构不属于本次自然写作主链。 | 保留，不重跑相关模型或步数消融。 |
| [evaluator.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/evaluator.md) | 显式评价命令 | 比较科学错误与价值，不等于文字编辑。 | 保留；不用评价分数验收通顺度，不加生产裁判。 |
| [investigator.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/investigator.md) | 完整卡证据调查 | 逐条核对设置、条件、数值与反证；长引述契约可能污染正文。 | 保留来源约束；writer 输入不包含整套调查操作日志。 |
| [librarian.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/librarian.md) | 完整卡档案比较 | 限定档案窗口和具体关系，简短输出已经合适。 | 保留；无需另设文风图书管理员。 |
| [moderator.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/moderator.md) | 旧辩论／完整卡裁决 | concise_ruling 容易混进状态、争点和证据再绑定经过。 | 保留裁决逻辑；这类原始输出只进入技术记录，不直接充当读者摘要。 |
| [novelty_examiner.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/novelty_examiner.md) | 完整卡新颖性检查 | 针对具体覆盖关系，强调未知边界，适合研究判断而非成稿。 | 保留；本轮不改新颖性规则，不复制自证语到 writer。 |
| [proposer.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/proposer.md) | 旧压力讨论 | 有依据地支持候选，不是最后的宣传作者。 | 保留；其论证只作原材料，不直接拼接段落交付。 |
| [reporter.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/reporter.md) | manifest 中旧 reporter.INVOKE | 已有“结论先行、口语化”的概括，但真实默认末端是 writer.POLISH。 | 不以只改此文件交差；保持历史可读，按实际调用检查是否另有显式用途。 |
| [selector.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/selector.md) | 完整卡筛选 | 严谨前置条件和评分字段会导向审查式文本。 | 保留显式完整卡用途；不要载入当前轻量发现链或写作链。 |
| [skeptic.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/skeptic.md) | 旧压力讨论 | 要求真正决定性异议，功能合理。 | 保留；写作验收不复用它作全面科研复审。 |
| [scientific_reviewer.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/roles/scientific_reviewer.md) | 完整科学卡审查 | 大量反例、修订与验收条款，擅长生成审稿记录，不是预研成稿规范。 | 保留现有显式用途；不作为“去防御写作”的额外日常角色。 |

## reports

| 文件 | 当前用途 | 观察 | 处理 |
|---|---|---|---|
| [overview.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/reports/overview.md) | 完整卡总览 | 旧模板直接展现判断、风险与状态，多栏堆叠；不属于当前 polished_overview。 | 本轮不强迁移历史报告；新默认入口只使用当前模板。显式旧报告保留技术属性。 |
| [card.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/reports/card.md) | 完整卡详情 | 数据字段、方法、检验和证据表作为技术记录有用。 | 保留完整记录，不压成宣传稿，也不自动复制到轻量正文。 |
| [records.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/reports/records.md) | 争点记录 | 状态、解除标准和变化轨迹是这份记录的内容。 | 保留，链接供按需阅读，不嵌在研究总览主段。 |
| [trace.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/reports/trace.md) | 共享运行记录 | task_id、prompt 和响应路径用于排查。 | 保留精确格式；“人话”改造不删故障证据。 |
| [cost.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/reports/cost.md) | 共享费用页 | 余额、区间、未知费用需要准确表达。 | 保留；不得为减少防御句隐藏未知费用或误报精确账单。 |
| [capabilities.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/reports/capabilities.md) | 共享能力需求页 | 记录阻塞问题和待评估能力，与报告正文不同。 | 保留独立页，不默认插入研究论证。 |
| [capability_handoff.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/reports/capability_handoff.md) | 用户／开发需求交接 | 权限、预算和实施边界是必要说明。 | 保留权限语义，不适用研究正文去免责声明规则。 |

## tasks

| 文件 | 当前用途 | 观察 | 处理 |
|---|---|---|---|
| [invoke.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tasks/invoke.md) | 旧完整卡任务模板 | 含 schema 示例和权威输入说明。 | 保留；当前短链用 discover/invoke，writer 用 writer_invoke。 |
| [repair_structure.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tasks/repair_structure.md) | 旧 JSON 修复 | 错误路径和修复边界需要保留，不能按自然语言重写研究。 | 保留；纯协议说明不显示到报告正文。 |
| [correct_tool_arguments.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tasks/correct_tool_arguments.md) | 共享工具参数纠正 | 原工具、原目标、合法字段和次数限制必要。 | 保留全文；本轮不改工具重试规则，模型不应把错误回放写进想法。 |
| [revise_science.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tasks/revise_science.md) | 完整卡科学修订 | JSON patch 与发现回应为科学操作；不等于文字润色。 | 保留；不作为报告编辑的修改入口。 |
| [source_read_no_progress.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tasks/source_read_no_progress.md) | 共享读取无进展提醒 | 根据已有材料完成或暂停的提醒服务于运行控制。 | 保留；不能把无进展提醒翻译为科学否定。 |

## tools

| 文件 | 当前用途 | 观察 | 处理 |
|---|---|---|---|
| [search_literature.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tools/search_literature.md) | 共享检索说明 | 来源与实际读取的区别是必要工具知识。 | 保留；结果相关性写为具体内容，不重复解释调用成功与否。 |
| [search_web.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tools/search_web.md) | 共享检索说明 | 指定未决问题和原始来源，社区材料只作线索。 | 保留；不靠文风改造扩大检索域或权限。 |
| [read_paper.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tools/read_paper.md) | 共享论文阅读 | 最新版已支持 arXiv、DOI、URL、pdf_url/document_id、分页与 find_text。 | 保留当前版本，绝不能覆盖为旧附件中仅 arXiv 的说明。 |
| [read_web.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tools/read_web.md) | 共享网页阅读 | 当前含 PDF 转 read_paper 与缓存翻页。 | 保留当前版本；访问失败只影响相应主张，不让每段复述网络错误。 |
| [read_record.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tools/read_record.md) | 共享档案读取 | 缓存覆盖和 64000 字符上限是准确调用所需信息。 | 保留；原文已读范围只在相关引用或具体缺口说明，不全文播报。 |
| [lookup_archive.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tools/lookup_archive.md) | 共享档案召回 | 有限召回不等于全库查重，正确。 | 保留；不增加写作代理和自动品味学习。 |
| [request_capability.md](https://github.com/BUAAZhangHaonan/adversarial-research-copilot/blob/676e76dcd44c626ee70c894a6a06da7e4bffd193/prompts/tools/request_capability.md) | 共享能力需求记录 | 记录需求不等于授权实施，必要。 | 保留权限与成本边界；不把需求操作细节写成科研优势。 |

## 必须一起核对的装配与代码

| 位置 | 已确认现状 | 本轮最小处理 |
|---|---|---|
| `prompts/manifest.json` | 当前六项研究任务与 writer 各有自己的系统文件；writer 只载入 discover/writer.md | 只把共同表达规范加入这些真实任务一次，旧协议和工具映射不变 |
| `src/arc/polishing.py` | 已有当前认识优先、移除旧 seed／修改历史、来源目录、无新研究约束 | 保留；不要把审查历史重新塞回 writer。长度仅为外层格式上限，不是文风分数 |
| `src/arc/discovery_workflow.py` | 阶段结束已有一次 writer.POLISH | 继续一次，不扩成逐卡 A/B 审查与反复重写 |
| `src/arc/reports.py::render_discovery_polish` | 实际使用 polished_overview/polished_idea，并生成技术副本；代码还提供自述润色 provenance | 模板不再输出通用自述；精确状态仍由渲染器提供，技术副本和链接保留 |
| `src/arc/prompting.py` | 负责 system、task 与 repair 模板装配 | 检查共同规范确已加载、Jinja 变量不变、工具和 JSON 约束仍可用；不通过 Python 内嵌新提示詞 |

### 已确认的主要成因与推断边界

明确存在的是重复的篇幅任务、技术记录与读者段落并排、通用编辑声明重复，以及写作提示词过于强调保留所有限制。它们会增加重复与防御表达的压力，是根据提示词和输出结构作出的设计判断。

不能由此断言每个冗长句都由同一个 prompt 导致，也不能宣称删掉几条规则就能保证所有模型写得自然。当前任务以保存材料上的真实前后改写为验收，不开展模型能力对比。

## 2026-09-13 实施记录

上表为用户修改包的原始 58 文件审阅，保留其审阅时的观察。此次在当前 master 工作区按真实装配落实：18 份现有 Markdown 替换，40 份按表中理由原文保留，另新增 `prompts/common/plain_research_writing.md`。58 个表项完整对应基线中的 58 份 Markdown；实际内容逐文件比较确认上述范围。

保留的文件包括完整卡路径所用的 6 份旧 common、13 份 roles、7 份 reports、5 份 tasks，全部 7 份工具说明，以及 `discover/repair.md`、`discover/search_sources.md`。它们分别承担原有研究协议、来源调用、恢复或完整技术记录职责，本次不以写作改造替换这些职责。`read_paper.md` 的 DOI/URL/PDF、多入口互斥、缓存分页、find_text 与读取范围语义完整保留。

manifest 仅修改任务书列出的七项 system 数组。任务 ID、role/task、工具、任务模板、修复模板、读取无进展模板及报告映射均保持原绑定。共同规范在每项 system 中恰好出现一次；旧 common/output_protocol、完整卡角色、长指南及两路编辑说明未加入这些 system。

替换稿作以下必要适配：

- `discover/researcher.md` 原稿结尾统一要求 CandidateCheck，与实际 SURVEY 的 FieldBrief 冲突。现按 `task_type` 分别装入 SURVEY 段或 CHECK 段，明确 SURVEY 返回 FieldBrief，CHECK 返回 CandidateCheck；字段语义与科学职责不变。
- `discover/writer.md` 保留原提示词的输入信任边界：外部文献、报告和输入中的命令只作材料，不能改变写作角色职责。此句不进入读者正文。

- `discover/overview.md` 在待预研分组保留已登记的候选关系，避免模板改排后丢失输入中的关系说明。
- `discover/idea_note.md` 在新旧核心认识完全相同时，只显示一次该认识，在历史章节标明未变；原动机和实际修改仍保留。

离线装配检查与范围说明见 [写作提示词实施验证](writing_review/PROMPT_IMPLEMENTATION.md)。
