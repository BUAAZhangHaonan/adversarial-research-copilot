# Prompt inventory

附录 A 的27份Markdown已按UTF-8 / LF原文提取，模板初稿没有改写。当前资产为23份全文相等、4份保留完整原稿前缀后追加：`roles/developer.md`、`roles/investigator.md`、`common/output_protocol.md`、`tools/read_record.md`。`tests/test_prompts.py::test_spec_assets_are_exact` 从任务书独立提取并检查这个边界；新增主张/缓存/metadata-only修复的远端整套已通过283项/52.08s，日志work/tests-claim-source.log；对应源码已提交为535357d08667ee192e246f8de0a126de0a544f0d；该git archive构建的独立wheel/sdist及/tmp安装资源验证通过，真实新run刚开始，尚无修复后科研E2E通过结果。Windows此前282项/427.42s是较早快照，不是最终283项结果。`manifest.json` 登记每个语义调用的角色、任务、公共片段、工具上限与报告模板。

## 登记的调用

| prompt_id | 额外规则 | 默认工具边界 |
|---|---|---|
| discovery.FRAME | 无 | 研究工具、档案读取 |
| discovery.NEXT_DRAW | selection_examples | 研究工具、档案读取 |
| discovery.COMPOSE | selection_examples、resource_policy | 研究工具、档案读取 |
| investigator.INVOKE / investigator.SCOPE_AUDIT | 无 | 研究工具、read_record、request_capability |
| librarian.INVOKE | 无 | lookup_archive、read_record |
| novelty_examiner.INVOKE | 无 | 研究工具、read_record |
| selector.INVOKE | selection_examples、resource_policy | 研究工具、read_record |
| developer.INVOKE / developer.IMPORT | resource_policy | 研究工具、read_record、request_capability |
| proposer.INVOKE / skeptic.INVOKE / moderator.INVOKE | 无；资源对象来自任务数据 | 研究工具、read_record |
| reporter.INVOKE | 无；仅登记，确定性报告不调用 | 无 |
| evaluator.INVOKE | selection_examples | 无；冻结证据对照 |

每份 system 固定按 research_policy → evidence_policy → output_protocol → role → 额外片段装配。任务数据、主体标识、机械 schema/样例进入 `tasks/invoke.md`。每次实际暴露的工具是 role 上限的子集，由 runtime 实际能力决定；没有工具不等于自动提供全部工具。

## 加载与恢复

- 默认 `PackageLoader('arc_prompt_assets', '')`，资产随 Python 包安装。明确给 `resource_root` 时使用 `FileSystemLoader`；没有从 cwd 或其他目录猜测资源的回退。
- `StrictUndefined` 阻止缺变量进入请求。缺资源、重复 manifest key、未登记调用/工具/引用模板、动态 include 或循环 include 均报错。
- `PromptLoader.render(prompt_id, {task_id, subject, payload, output_example?}, schema=..., tool_profile=...)` 返回 `RenderedPrompt`。
- `RenderedPrompt` 保存 messages、源文全文、每个源文件 SHA-256、完整依赖、工具说明和总渲染 hash。`save_snapshot` / `load_snapshot` 不依赖当前模板，恢复时核验源与渲染完整性。
- 结构修复使用同一登记角色的 system，task 改为 `repair_structure.md`，接受 previous_response 与 validation_errors；次数由 runtime 限为一次。
- 输入材料只 JSON 序列化一次插入，不再调用模板解析。资料里的 `{{ ... }}`、代码和花括号是数据，不执行，也不把它们误当未填模板。

## 确定性报告

附录 overview/card 保留原文。新增 `reports/records.md`、`trace.md`、`cost.md`、`capabilities.md` 用于未保留原因、争点、已保存调用材料、费用和缺能力记录，全部进入 manifest。

`render_run(store, run_id, output_dir, prompt_loader=None)` 只读取权威记录，输出 `REPORT.md`、stable card ID/version 下的详情、`PROMPT_TRACE_INDEX.md`、`COST_REPORT.md` 和按需 `MCP_REQUIREMENTS.md`。已验收对象另存 JSON 方便核对。它不调用 reporter、不改变 selection/assessment、不把 scope change 发展为下一张卡。

## 校验边界

测试覆盖逐字模板、所有登记角色、缺模板/变量、重复 ID、未登记工具、一次数据插入、结构修复保留原规则、快照篡改、异 cwd 包加载、Markdown 链接、中文和特殊字符、稳定 ID、零卡、暂停状态及确定性重建。

AST 检查只扫描 `src/arc`：SDK 仅允许 `runtime.py`，拒绝上游直接模型请求、任意 system_prompt/user_prompt、from_string、工具内联 description 与内联 system/user 消息。`references/` 不扫描。该检查证明代码调用边界，不证明科学判断质量；实际 provider 调用、重试次数、schema 接受条件与费用由 runtime/store 测试验证。

## 有依据的初稿调整

2026-09-07：原文 27 份已先逐字提取。为落实任务书 4.2/4.3 对独立用户问题/提案的导入，在 `roles/developer.md` 原文后增加仅适用于 `developer.IMPORT` 的小节，并登记该 task。它固定 runtime 的 ProblemAnchor，把用户文字整理成初始卡，不将用户陈述当已核验外部证据，不依赖不存在的 discover 通过标记，不抽卡或生成转向。其结果沿用 DeveloperResult。原附录正文保持逐字前缀；测试逐字检查前缀并单独检查 IMPORT 边界。这是补齐入口的工程契约调整，不宣称由真实模型质量对照证明更优。

2026-09-07：为让 investigator 输出与实际工具 trace 可确定性对齐，在 `roles/investigator.md` 原文后增加搜索映射小节：actual_searches 逐项覆盖成功的 search_literature/search_web，精确复制 trace_id、wrapper operation、submitted query/theme_document 与 returned source_ids；读取/档案调用不混算为搜索，失败保留为 access limit。原附录正文仍逐字保留。此调整对应 runtime 的 trace 对照验证，不是额外科研规则。

2026-09-07：为使定向补证能连接已有争点，在 `roles/investigator.md` 后追加目标主张协议。调查当前 claim/issue 时明确复制任务给出的 claim_id 与 claim_version；新背景观察两者均为 null，不通过文本相似度猜依赖，不让旧版本证据自动支持改版主张。此调整配合 Finding 的成对可空字段和 Store 外键验证；提示词测试只证明协议进入模型输入，实际证据注册与争点关闭由 Store/runtime 测试覆盖。

2026-09-07：依据真实开发 V2 调查的引用和范围错误，仅在 investigator 末尾追加连续原文摘录、metadata/snippet 与事实/推断范围的通用规则及短反例。原文全文 hash 前缀不变。失败原件、逐项类别、理由及未完成的 V3 验证见 [PROMPT_CALIBRATION](PROMPT_CALIBRATION.md)；未使用留出主题调参。

2026-09-07：`common/output_protocol.md`在原文后追加 `Evidence request ownership`，随2b8b79a记录。已有卡的请求必须关联当前输入中的claim/issue/draw；尚无卡且尚无这些实体时才允许使用真实task/run上下文。它不允许从无关档案或工具文本借用ID，不把可空字段解释为无目标的无限补证许可。

2026-09-07，535357d已提交且离线整套通过：依据L2显式开发输入的真实读取误报，在 `tools/read_record.md` 原文后追加 `Cached source coverage`。它区分 `cached_content_chars` / `more_cached_content` 与原来源的 `content_total_chars` / `content_complete`；`requires_source_fetch=true` 表示缓存读尽且来源尚不完整，read_record不能获取缺失原文。模型只能使用实际已开放的read_web/read_paper补取，或记录访问限制；缓存末尾不能作为全文不存在某条件的证据。完整缓存也不等于角色实际读过全部相关窗口。该调整是工具字段语义澄清，不改变科研品味、任务范围或证据通过门槛。

同批主张修复没有另写内联prompt：CardDraft的claims变为必填，新增删除主张复核和结构化角色目标校验；当前schema仍经 `tasks/invoke.md` 渲染，proposer自由文本不被当作ID。具体失败原件、代码/测试映射和未验证边界见 [CLAIM_AND_SOURCE_FIXES](CLAIM_AND_SOURCE_FIXES.md)，科学内容抽查见 [L2_EVIDENCE_REVIEW](L2_EVIDENCE_REVIEW.md)。原付费回复、accepted对象和旧卡不人工补回或重写；新资源改变hash，不把旧快照改装成新提示词结果。

2026-09-07：同一Cached source coverage小节另补metadata-only边界：没有已存正文时，read_record明确返回content=null、content_complete=false、cached_content_chars=0、more_cached_content=false、requires_source_fetch=true；重复读取同一未变化来源不能生成正文。搜索snippet仍是metadata。新搜索来源登记以bool(text)作为完整度缺省值，旧无正文来源的错误complete标记只在返回视图中澄清，不改写历史原件。

这次补充对应真实独立run的连续215次空正文读取；最近40次是20个来源各读2次。开发者的临时单run INSERT准入阻断让已开始请求完整结算后暂停，随后已删除；它不是生产自动循环检测，也未更改预算。失败原件与暂停边界见 [L2_EVIDENCE_REVIEW](L2_EVIDENCE_REVIEW.md)。283项离线通过不能证明模型在修订说明后已停止重复空读。

安装验证日志：work/wheel-build-535357d.log、work/wheel-install-535357d.log、work/wheel-help-535357d.log；安装在独立.venv-wheel，从/tmp加载包资源。本次文档更新起点为3f6026f，代码验收版本仍为535357d；安装成功不能替代L2/L3/L4真实结果。
