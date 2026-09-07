# Prompt inventory

附录 A 的 27 份 Markdown 已按 UTF-8 / LF 原文提取，`tests/test_prompts.py::test_spec_assets_are_exact` 与任务书逐字比较。模板初稿没有改写。`manifest.json` 登记每个语义调用的角色、任务、公共片段、工具上限与报告模板。

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
| developer.INVOKE | resource_policy | 研究工具、read_record、request_capability |
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
