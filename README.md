# ARC — 文献驱动的研究灵感与可行性预研

ARC 帮助人找到有新意、有意义、值得继续讨论的研究方向。默认工作链是：

**共享领域调查 → 一张短灵感 → 快速价值筛选 → 仅对入围想法补查文献与可行性 → 交给人选择。**

事实需要准确，假设可以大胆，无法判断的部分明确留下。实验、完整论证和论文由人完成。系统不保证生成好选题，也不把模型的自评当作科研认证。整体结构见[架构与关键角色](docs/ARCHITECTURE.md)，发现主干见 [Discover First](docs/DISCOVER_FIRST.md)。只维护 `master`，保留细粒度提交。

## 安装与开始使用

Python 3.11+。在项目目录安装锁定依赖，复用已配置的模型凭据与 MCP 服务：

```bash
uv sync --locked --extra dev
source .venv/bin/activate
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data discover "研究主题" --draws 5 --budget-cny 20
```

一次主题最多五次构思机会，共享调查与预算，不要求用满。每次先保存 `IdeaSeed`，编辑决定是否继续投入；普通或重复想法尽早放下，有启发但暂时无法核查的想法可以暂存。只有入围候选继续 `CHECK`，形成短 `IdeaNote`。默认 discover 不先生成完整 `CardDraft`，不串联全面审查、修订、复核或排序裁判。

每完成一项调查或候选记录就更新本地 Markdown。输出位于 `DATA_DIR/reports/RUN_ID/`；预算暂停时，已经保存但未完成预研的灵感仍可查看。

## 人选择之后再进入后续阶段

从报告取得稳定的 `IDEA_ID`，显式选择后续任务：

```bash
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data develop --idea IDEA_ID --budget-cny 20
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data run --idea IDEA_ID --budget-cny 20
```

`develop --idea` 补充近邻比较、最简实现路线、资源与风险；`run --idea` 讨论影响是否值得继续的前提和替代解释。两者直接接收轻量想法及已有调查，不填造完整研究卡、不自动启动研究实验，也不要求消除所有科学未知。每个阶段独立结束，由人决定下一步。

已有完整卡仍可显式使用 `develop/run --card CARD_ID --version N`；已有问题或文档仍可使用 `--question "具体问题"`、`--proposal proposal.md`。这些是保留的完整卡/问题路径，可能执行原有较完整的方案和科学审查逻辑，不是新 discover 的隐含步骤。`--idea`、`--card`、`--question`、`--proposal` 每次选一个。`import-card card.json` 继续接受完整 `CardDraft` JSON。

## 读什么、怎样理解状态

| 输出 | 内容 |
| --- | --- |
| `REPORT.md` | 阶段完成后含阶段摘要与研究总览；中途明确标为技术稿 |
| `TECHNICAL_REPORT.md`、候选 `.technical.md` | 润色前的研究原稿，保留全部技术细节 |
| `ideas/IDEA_ID.md` | 短灵感或已完成的预研卡，含相关来源及阅读边界 |
| `FIELD_BRIEF.md` | 共享领域现状、路线关系、开放切入点和关键资料 |
| `SEARCH_SOURCES.md` | 全部检索命中审计；不是正式引文清单 |
| `PROMPT_TRACE_INDEX.md` | 已保存提示词、任务结果和原始调用材料入口 |
| `COST_REPORT.md`、`DISCOVERY_USAGE.json` | 费用、实际请求/工具动作、token及首个产物时间 |

`discuss` 是值得讨论，`lead` 是有条件线索，`drop` 是本次放下；都不是永久科研判决。编辑的 `park` 保留未做定向预研的线索。`pending` 表示任务尚未完成，不能当作推荐。执行状态 `COMPLETED`、`PAUSED_BUDGET`、`PAUSED_PROTOCOL` 等与研究判断分开：预算或工具暂停不等于想法被否定。

SourceNote 记录原始来源 ID、相关性、实际阅读层级和限制。检索摘要不等于全文，来源可定位不等于其推论正确；新假设不强制拥有逐主张的“verified”证据。全文按需从缓存分页读取，`read_record` 单次上限为 64000 字符。CHECK 会把修正后的核心认识、已撤回前提和决定性未知交给下一次抽卡，并按需更新共享简报。TRIAGE 比较本轮已有候选，档案召回返回当前去留与修正理由。已有相关阅读笔记足够时直接复用，报告明确区分复用与本任务新增工具动作。阶段结束时，撰稿员基于已保存材料做一次最终润色：先讲核心问题、思路、近邻技术和主要风险，首次术语用中文解释，保留学术条件与不确定性。新任务阶段摘要上限450字符、总览1100字符、每候选1300字符，每自然段不超过260字符；超限使用一次纠错，必要细节另留技术稿。写作目标比上限更短，关键文献通常3–5篇。撰稿员不重新检索，也不改数据库中的科学判断。原始响应、历史失败与费用保留，私有 reasoning 不进入研究报告。

## 模型配置与预算

科研 Markdown 不绑定具体型号。`research_model` 指向配置中的模型别名，默认 `scout`、`ideator`、`editor`、`writer` 共用该别名；需要时由人显式覆盖角色。当前所有默认角色统一使用官方名称 `deepseek-flash`，配置别名与实际 API 名一致。`max` 与完整输出上限保持不变，当前峰谷价格及历史任务边界见[型号迁移记录](docs/MODEL_MIGRATION_20260910.md)。

```yaml
research_model: deepseek-flash
roles:
  scout: deepseek-flash
  ideator: deepseek-flash
  editor: deepseek-flash
  writer: deepseek-flash
```

```bash
arc --config runtime.yaml --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data discover "研究主题"
```

别名在 `models` 中配置 `provider`、实际 `model`、凭据环境变量、能力和上限；计费配置必须与实际型号及上限一致。当前适配 `deepseek` 和符合已支持 Chat Completions/JSON/工具调用/streaming usage 协议的 `openai_compatible` 端点。未知别名、缺少凭据或不支持的操作明确报错。供应商专有协议仍需独立适配，不能认为已兼容所有服务；详见 [配置边界](docs/DISCOVER_FIRST.md#模型配置边界) 和 [配置样例](configs/runtime.yaml)。不会自动降档或购买新服务。

运行前会显示预计费用，并尽力查询DeepSeek余额；余额不足告警，查询失败只给估计并继续。预计范围不是费用保证或硬上限，详见[成本与余额提示](docs/PREFLIGHT_COST_AND_BALANCE.md)。

每个用户阶段默认 20 元；SURVEY、SKETCH、TRIAGE、CHECK 共用本次 discover 账本。每次付费请求前按完整响应上界预留；已开始回复自然完成，余额不足暂停下一请求。预留不是实际花费，不清零历史，不把未知费用当作零。

```bash
arc --data-dir /path/to/private/arc-data status RUN_ID
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data resume RUN_ID
```

恢复沿用已保存任务、原 draw 与预算。工具参数错误和最终 JSON 错误每项 Agent 任务各有一次纠正机会；开发中的显式修复不等于自动增加任务纠错额度。协议与显式重试见 [协议纠正](docs/PROTOCOL_CORRECTION.md)；有限线索的缺证暂缓、写作上限和原稿保留见[成文与缺证交接](docs/WRITING_AND_EVIDENCE_HANDOFF.md)。能力需求交给用户评估和实施，正式服务不依赖 CodeX；见 [改进需求](docs/CAPABILITY_REQUESTS.md)。

## 开发验证记录

当前用户主题的五卡任务、最终成文实测与费用见[9月10日交付记录](docs/HALLUCINATION_STUDY_DELIVERY_20260910.md)。

```bash
uv run pytest tests/test_discovery_workflow.py tests/test_discovery_reports.py tests/test_model_adapters.py -q
```

检查默认轻量对象、早筛停止、共享材料更新、五次机会与恢复、人工交接、型号别名与已安装 Markdown 资源，再进行必要整体回归和正常打包。

2026-09-10 较早一轮“当前认识复用”的改进验证覆盖：新模型配置与计价、当前认识回写、同轮候选比较、档案召回和报告呈现；少量真实调用复用已审阅材料，不重跑整个五卡样例，不作模型质量排行榜。开发费用由用户授权按需分配，不因上一轮40元限制停止；生产阶段默认20元仍由使用者显式调整。结果、输入缩减口径及真实费用见[该轮记录](docs/CURRENT_UNDERSTANDING_20260910.md)。其“不重跑五卡”边界只适用于当时的校准任务；后续用户授权的幻觉与能力边界研究另行运行五次抽卡。

9月9日两个开发样例已经完成，原产物、失败与费用见[续跑记录](docs/DISCOVER_FIRST_CONTINUATION.md)。人工阅读判断想法是否有意义、是否只是改名重复、背景是否有依据和阅读成本是否合理。执行完成不代表科学质量通过，也不证明超过单模型。

旧 `test-e2e`、`test-compare`、`test-ablation` 保留为显式历史开发工具，不是安装步骤、默认产品路径或本轮必跑验收。以前的结果与费用不回写为本轮通过，参见 [历史功能验收](docs/FUNCTIONAL_VALIDATION_RESULTS.md)、[历史收尾](docs/FINAL_CLOSEOUT.md)。
