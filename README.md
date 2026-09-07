# ARC — 研究 idea 抽卡与可行性分析

ARC 帮助研究者找到值得调查的问题，形成可比较的研究卡，再展开方案和压力测试。
实验和论文由人完成。`PROMISING` 表示值得下一步调查，不表示结果已证明或论文会被录用。

当前代码只维护master。同一自然卡 discover → develop → run 三阶段执行完成。工程验证与三组对照的实际结果、费用和科学边界见[当前收尾状态](docs/MASTER_STATUS.md)。

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
次数不是产出目标，零张推荐卡也是合法结果。每次聚焦一个问题族和一张卡，同族控制项不另算方向。
develop 保留问题和原卡，改方法生成新版本；遇到必须靠实验解决的争点，写出最小验证后停止。

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
主张内容或条件改变却遗漏递增时，runtime 记录并派生新版本。新版移除同目标旧版本证据引用，
由 Agent 重新选择或补充证据；原卡、旧证据和原始响应保留。受引用移除影响的裁决经过补证后重新判断。

每个 run 输出 `REPORT.md`、单卡详情、`PROMPT_TRACE_INDEX.md` 和 `COST_REPORT.md`。
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

开发验证始终复用同一个 `.arc-validation/arc.sqlite` 和 100 元父账户，不能改目录重新获得预算。
先完成工程契约（L1），再实际入口（L2）、自然发现同卡贯穿（L3）和同材料小规模对照（L4）。
开发命令的串联不改变正式命令默认停止。自动评价只是初步检查，不代替研究者认可。
实际完成范围、成本与阻塞见 `docs/E2E_REPORT.md`、`docs/COST_REPORT.md` 和 `docs/IMPLEMENTATION_AUDIT.md`。

[任务要求](EXECUTION_SPEC.md) · [提示词清单](docs/PROMPT_INVENTORY.md) · [迁移说明](docs/MIGRATION.md)
