# ARC — 文献驱动的研究灵感与可行性预研

ARC 帮助人找到有新意、有意义、值得继续讨论的研究方向。默认工作链是：

**共享领域调查 → 一张短灵感 → 快速价值筛选 → 仅对入围想法补查文献与可行性 → 交给人选择。**

事实需要准确，假设可以大胆，无法判断的部分明确留下。实验、完整论证和论文由人完成。系统不保证生成好选题，也不把模型的自评当作科研认证。本轮接线与验收状态见 [Discover First](docs/DISCOVER_FIRST.md)。只维护 `master`，保留细粒度提交。

## 安装与开始使用

Python 3.11+。在项目目录安装锁定依赖，复用已配置的模型凭据与 MCP 服务：

```bash
uv sync --locked --extra dev
source .venv/bin/activate
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data discover "研究主题" --draws 5 --budget-cny 20
```

一次主题最多五次构思机会，共享调查与预算，不要求用满。每次先保存 `IdeaSeed`，编辑决定是否继续投入；普通或重复想法尽早放下，有启发但暂时无法核查的想法可以暂存。只有入围候选继续 `CHECK`，形成短 `IdeaNote`。默认 discover 不先生成完整 `CardDraft`，不串联全面审查、修订、复核、付费报告员或排序裁判。

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
| `REPORT.md` | 核心想法、意义、风险及当前去留；待预研单列 |
| `ideas/IDEA_ID.md` | 短灵感或已完成的预研卡，含相关来源及阅读边界 |
| `FIELD_BRIEF.md` | 共享领域现状、路线关系、开放切入点和关键资料 |
| `SEARCH_SOURCES.md` | 全部检索命中审计；不是正式引文清单 |
| `PROMPT_TRACE_INDEX.md` | 已保存提示词、任务结果和原始调用材料入口 |
| `COST_REPORT.md`、`DISCOVERY_USAGE.json` | 费用、实际请求/工具动作、token及首个产物时间 |

`discuss` 是值得讨论，`lead` 是有条件线索，`drop` 是本次放下；都不是永久科研判决。编辑的 `park` 保留未做定向预研的线索。`pending` 表示任务尚未完成，不能当作推荐。执行状态 `COMPLETED`、`PAUSED_BUDGET`、`PAUSED_PROTOCOL` 等与研究判断分开：预算或工具暂停不等于想法被否定。

SourceNote 记录原始来源 ID、相关性、实际阅读层级和限制。检索摘要不等于全文，来源可定位不等于其推论正确；新假设不强制拥有逐主张的“verified”证据。全文按需从缓存分页读取，`read_record` 单次上限为 64000 字符。报告直接渲染已保存对象，不另付费重述。原始响应、历史失败与费用保留，私有 reasoning 不进入研究报告。

## 模型配置与预算

科研 Markdown 不绑定具体型号。`research_model` 指向配置中的模型别名，默认 `scout`、`ideator`、`editor` 共用该别名；需要时由人显式覆盖角色。当前接入仍为 DeepSeek V4 Flash/Pro，默认主模型为 Pro，当前 DeepSeek 的 `max` 与完整输出上限保持不变。

```yaml
research_model: deepseek-v4-pro
roles:
  scout: deepseek-v4-pro
  ideator: deepseek-v4-pro
  editor: deepseek-v4-pro
```

```bash
arc --config runtime.yaml --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data discover "研究主题"
```

别名在 `models` 中配置 `provider`、实际 `model`、凭据环境变量、能力和上限；计费配置必须与实际型号及上限一致。当前适配 `deepseek` 和符合已支持 Chat Completions/JSON/工具调用/streaming usage 协议的 `openai_compatible` 端点。未知别名、缺少凭据或不支持的操作明确报错。供应商专有协议仍需独立适配，不能认为已兼容所有服务；详见 [配置边界](docs/DISCOVER_FIRST.md#模型配置边界) 和 [配置样例](configs/runtime.yaml)。不会自动降档或购买新服务。

每个用户阶段默认 20 元；SURVEY、SKETCH、TRIAGE、CHECK 共用本次 discover 账本。每次付费请求前按完整响应上界预留；已开始回复自然完成，余额不足暂停下一请求。预留不是实际花费，不清零历史，不把未知费用当作零。

```bash
arc --data-dir /path/to/private/arc-data status RUN_ID
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data resume RUN_ID
```

恢复沿用已保存任务、原 draw 与预算。工具参数错误和最终 JSON 错误每项 Agent 任务各有一次纠正机会；开发中的显式修复不等于自动增加任务纠错额度。协议与显式重试见 [协议纠正](docs/PROTOCOL_CORRECTION.md)。能力需求交给用户评估和实施，正式服务不依赖 CodeX；见 [改进需求](docs/CAPABILITY_REQUESTS.md)。

## 本轮开发验收

```bash
uv run pytest tests/test_discovery_workflow.py tests/test_discovery_reports.py tests/test_model_adapters.py -q
```

检查默认轻量对象、早筛停止、共享材料更新、五次机会与恢复、人工交接、型号别名与已安装 Markdown 资源，再进行必要整体回归和正常打包。

**本轮真实验证最多两个 discover，各自上限 20 元，累计不超过 40 元且受现有已授权父账本剩余额度约束。** 不根据历史余额新建授权，不加额凑满五次。使用开发样例“多模态模型在真实任务中何时需要主动获取额外信息”和“具身智能在环境变化后如何使用和更新既有经验”；不预填答案、数据集或方法。具体完成情况与花费以 [本轮记录](docs/DISCOVER_FIRST.md#验证记录) 为准。

人工阅读判断想法是否有意义、是否只是改名重复、背景是否有依据和阅读成本是否合理。最多针对一个主要问题调整一轮；若额外真实复核仍共用累计 40 元。允许没有推荐结果，不宣布科学质量通过或超过单模型。此次不运行 Flash/Pro、A–E 对照，也不为形式上的全链成功付费串联 develop/run；后续交接可离线验证。

旧 `test-e2e`、`test-compare`、`test-ablation` 保留为显式历史开发工具，不是安装步骤、默认产品路径或本轮必跑验收。以前的结果与费用不回写为本轮通过，参见 [历史功能验收](docs/FUNCTIONAL_VALIDATION_RESULTS.md)、[历史收尾](docs/FINAL_CLOSEOUT.md)。
