# ARC — 研究 idea 抽卡与可行性分析

ARC 帮助研究者找到值得调查的问题，形成可比较的研究卡，再展开方案和压力测试。
实验和论文由人完成。`PROMISING` 表示值得下一步调查，不表示结果已证明或论文会被录用。

当前代码只维护 master。新默认流程以核心洞察和实质纠错为主线；本轮改动与验证边界见[功能重构进度](docs/FUNCTIONAL_REDESIGN.md)。此前三组对照和自然运行保留为历史开发记录，不能作为新流程已经改善研究质量的证明。

## 安装和运行

Python 3.11+。在 g203 的项目目录安装锁定依赖；现有 MCP 服务只连接，不修改。

```bash
uv sync --locked --extra dev
source .venv/bin/activate
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data discover "研究主题" --draws 5 --budget-cny 20
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data develop --card CARD_ID --version 1 --budget-cny 20
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data run --card CARD_ID --version 2 --budget-cny 20
```

三个入口默认各自结束即停。一次 discover 的最多五次机会共用 20 元和同一份原始文献；
次数不是产出目标，零张推荐卡也是合法结果。每次由 Pro 连贯构思一张卡，独立审查关键事实、逻辑和研究价值；有必要时定向修订一次并复核。修订不新增抽卡机会。
develop 用于用户选中后的方案展开，run 用于独立压力检查。两者沿用科学审查和必要修订，不默认追加旧多角色辩论。原始研究范围保持稳定，模型提出的方法、数据集和指标可以修改。实验尚未执行时只交付可行性分析和最小验证方案。

已有问题可以直接使用 `develop --question "具体问题"` 或 `run --proposal proposal.md`，
无需先 discover。`import-card card.json` 接受严格的 ResearchCard draft JSON。
`--card`、`--question` 和 `--proposal` 三选一。

```bash
arc --data-dir /path/to/private/arc-data status RUN_ID
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data resume RUN_ID
# 仅在用户明确追加授权时使用；父预算不会因此重置。
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data resume RUN_ID --add-budget-cny 5
```

CLI 显式参数优先于 `--config runtime.yaml`，未填写的选项使用配置值。已开始 run 的配置和提示词
冻结；研究输入改变需要新 run。原任务协议失败后的显式新版本入口见[协议纠正](docs/PROTOCOL_CORRECTION.md)，保留原失败与同一预算。长时间中断不清除旧调查，也不宣称恢复服务丢失的生成流。
远端长期运行可由用户用 `nohup`/tmux 启动 ARC，SSH 断开不影响该独立进程。

## 卡片、证据和记忆

卡片解释问题价值、最接近工作差异、假设与替代解释、可辨识的最小检验和 3090/A100 资源范围。
主报告允许有依据但尚未实验的合理假设；关键前提不明的卡进入待补证。
无必要性的模块拼接不能通过。组合例外同时要求可信的实际改善理由、新机制预测与同预算检验。

SQLite 保存状态、版本、争点、来源索引和预算；原文、模型原始消息、提示词快照和工具返回保存为私有文件。
报告是可重建视图。来源由 runtime 登记，二级模型分析不会被当成已经核对的原文。
中文 FTS 召回只找可能相似的历史卡，再比较问题、机制和知识增量；不自动学习用户品味。

新主张可以引用已有观察作为背景依据；报告和后续角色会看到这类引用不会转移原主张的验证状态。
直接针对主张的证据仍绑定其 ID 和版本。旧版本证据不能直接用于新版主张，也不能靠背景引用关闭经验争点。
独立科学审查区分表达修正与实质主张变更。前者保留语义版本并记录等价审查，后者派生新版本，只移除并复核受影响的支持关系；原卡、来源、旧证据和原始响应保留。
证据的 `verified` 仅表示摘录可在原文定位，不能证明它支持卡片的解读。数字归属、适用条件、分母、因果推断和最近工作差异仍须科学审查。

每个 run 输出 `REPORT.md`、单卡详情、`PROMPT_TRACE_INDEX.md` 和 `COST_REPORT.md`。主报告先呈现洞察、价值、最小检验与关键风险；只有实际引用进入正式来源。检索中碰到的其他链接放在 `SEARCH_SOURCES.md`，不自动进入后续工作材料。
缺少工具能力或提出改进需求时输出 `MCP_REQUIREMENTS.md`，正式运行默认交给用户评估和实施。
`requirements list/review/export` 支持比较方案并导出用户执行说明；不会自动改限额或创建任务。
开发时可显式选择 CodeX 评估；正式服务不依赖 CodeX。使用说明见[改进需求流程](docs/CAPABILITY_REQUESTS.md)。
`read_record` 单次上限现为 64000 字符，仍按需要读取和分页。
原始 reasoning 只用于协议恢复与私有调试，不进入报告。
真正的新问题只产生一个冻结建议；明确批准后用 `restart-direction RUN_ID --approve-scope-change`
从新 seed 重新开始，不继承旧通过状态。

## 模型和预算

仅 DeepSeek V4 Flash / Pro，所有语义调用（含结构修复、开发评价）显式 `max`。
模型 SDK 禁用自动重试，使用原生 Chat Completions streaming/tool calls，保存完整 reasoning/tool关联。
正文非空不等于成功；截断、非法结束或不完整对象不能参与科研判断。

每个 Agent 任务的最终 JSON 结构错误和工具参数错误各有一次纠正机会，两类分别计数。非法工具参数执行前被拒绝，
错误字段及实际 schema 反馈给模型；只允许修改报错字段，原工具、目标和合法字段保持不变。
工具纠正成功后可以继续正常调用工具；同类纠正再次失败才暂停。最终 JSON 修复仅整理响应，不重新启动研究工具。无法核对原目标的非法 JSON 参数可提交
blocked 改进需求；不能通过任意替换目标继续执行。详见[协议纠正](docs/PROTOCOL_CORRECTION.md)。
调查引文无法对应原文时，原任务保留为失败；可另开一次受同一预算约束的
原文复核，重新读取已登记材料，逐字校验后才登记证据。复核仍失败就暂停，不自动改写引文或科研结论。

每次付费请求前按官方完整输出上限预留。正在进行的回复自然完成，额度不足只暂停下一次请求。
预留金额不是实际支出。费用按人民币整数微元记账，reasoning 不重复计入输出；缺失费用不写成零。
价格来源和核查时间见 `configs/pricing.json`；新请求使用经复核的价格快照，旧账目保持原样。

g203 当前可核查的网页搜索/读取、论文原文读取路径已记录费用依据。
ScholarTrace 的内部收费查询尚无可靠费用上界，不作为可执行工具注入；其能力仍保留在清单中。
详细边界见 [服务审计](docs/SERVICE_AUDIT.md)。不要修改 MCP 服务来绕过预算。

## 开发验收

```bash
uv run pytest -q
arc --env-file /path/to/existing/.env --data-dir /path/to/private/validation test-e2e --allow-stage-transition
arc --env-file /path/to/existing/.env --data-dir /path/to/private/validation test-compare --source-run RUN_ID
```

开发验证复用同一个私有 `.arc-validation/arc.sqlite` 和已有父账户，追加预算必须有用户授权，不能改目录重置花费。本轮沿用用户已追加的账户余额授权；正式阶段默认仍为 20 元。
新验证先检查四组正误对照的发现、修订与复核，再做同材料构思/模型/审查消融和新主题迁移，最后验证同卡三入口。原先三个主题均已成为开发回归，不能再称作未见留出集。
开发命令的串联不改变正式命令默认停止。自动评价只是初步检查，不代替研究者认可。
实际完成范围、成本与阻塞见 `docs/E2E_REPORT.md`、`docs/COST_REPORT.md` 和 `docs/IMPLEMENTATION_AUDIT.md`。

[本轮功能要求](docs/FUNCTIONAL_REDESIGN_REQUEST.md) · [原任务要求](EXECUTION_SPEC.md) · [提示词清单](docs/PROMPT_INVENTORY.md) · [迁移说明](docs/MIGRATION.md)
