# Adversarial-Research-Copilot (ARC)

An adversarial multi-agent framework for iterative research idea critique, refinement, and convergence.

ARC 不是“自动做科研”的黑箱流水线，而是一个受控对抗式论证引擎：
- Proposer：把方案推到最强版本。
- Skeptic：系统性找漏洞并要求可验证证据。
- Moderator：只做结构化裁决和收敛判定。

## Why ARC

单模型自审容易陷入盲点。ARC 强制跨角色、跨模型对抗评审，让输出从“聊天记录”变成可落地的 Research Decision Memo。

## What We Borrowed (And Why)

基于对 ARIS 与 EvoScientist 的实仓审阅，ARC 在 v0.1.0 版本收敛出三项升级：
- 跨模型对抗约束：支持启用 Proposer 与 Skeptic 的跨模型对抗；当前默认配置不强制 Proposer 与 Skeptic 使用不同模型，但可在 `configs/debate.yaml` 中开启。
- 可恢复循环：每轮写入 `run_state.json`，支持 `--resume` 从中断点继续。
- 结构化裁决协议：Moderator 追加 machine-readable YAML，提升解析稳定性。

取舍：
- 借鉴 ARIS 的“轻量、可恢复、流程严控”。
- 吸收 EvoScientist 的“记忆与多阶段理念”。
- 暂不引入重框架编排，先把对抗收敛引擎打磨到可复用。

## Local References (Visible In Repo)

为便于对照学习，项目内提供两类参考资源：

1) 本地参考仓库同步目录（可随时更新）：
- `references/ARIS`
- `references/EvoScientist`

2) 已纳入版本库的主题参考文献目录（当前包含 RLHF 相关 PDF）：

说明：`references/*` 主要用于本地对照审阅；`docs/reference/*` 作为项目文献资产可随仓库版本管理。

```bash
bash references/sync_references.sh
```

说明：`references/*` 主要用于本地对照审阅；`docs/reference/*` 作为项目文献资产可随仓库版本管理。

## Skills Library

ARC 已提供一套技能化工作流（见 `skills/`）：
- `research-lit`
- `idea-creator`
- `novelty-check`
- `research-refine`
- `experiment-bridge`
- `debate-runner`
- `auto-review-loop`
- `memo-synthesis`
- `evidence-grounding`
- `recovery-resume`
- `pipeline-arc`

这套库借鉴 ARIS 的轻量技能组织方式，但围绕 ARC 的 Proposer/Skeptic/Moderator 对抗收敛逻辑重写。

## Architecture

```text
User Research Idea
        |
        v
 Problem Framer
        |
        v
 Shared Research State
        |
        +------------------------------+
        v                              v
    Proposer                       Skeptic
        |                              |
        +--------------+---------------+
                       v
                   Moderator
      (scorecard / blockers / revisions / stop)
                       |
         +-------------+-------------+
         v                           v
   Continue Loop               Converged Memo
```

## Debate Protocol

当前 debate prompt 采用“人类可读分析 + 固定 YAML 尾部”协议：

- Proposer：主张一个首选方案，回应上一轮 blocker / revision，并在结尾输出 `proposal_quality`、`top_next_actions`、`open_questions`。
- Skeptic：聚焦最致命风险、证据缺口与必须回答的问题，并在结尾输出 `risk_summary`、`next_round_focus`、`evidence_to_collect`。
- Moderator：给出整体裁决、`scorecard`、`unresolved_blockers`、`required_revisions` 与 `continue_or_stop`。

说明：人类可读部分允许灵活组织，但机器可读字段名是稳定契约，详见 `docs/prompt-contracts.md`。

## Convergence Rules

默认停止条件：
- 连续 2 轮无未解决 blocker。
- 平均分 >= 4.0。
- 至少完成 2 轮。
- 或 Moderator 显式给出 STOP。

## Project Structure

```text
adversarial-research-copilot/
├─ README.md
├─ LICENSE
├─ pyproject.toml
├─ .env.example
├─ configs/
│  ├─ chat_mode.yaml
│  ├─ references.yaml
│  ├─ models.yaml
│  ├─ runtime_models.yaml
│  └─ debate.yaml
├─ prompts/
│  ├─ proposer.md
│  ├─ skeptic.md
│  ├─ moderator.md
│  └─ chat_mode/
│     ├─ proposer_chat.md
│     ├─ skeptic_chat.md
│     └─ moderator_chat.md
├─ src/arc/
│  ├─ cli.py
│  ├─ orchestrator.py
│  ├─ state.py
│  ├─ schemas.py
│  ├─ memory.py
│  ├─ llm_client.py
│  ├─ model_registry.py
│  ├─ providers/
│  │  └─ literature.py
│  ├─ agents/
│  │  ├─ proposer.py
│  │  ├─ skeptic.py
│  │  └─ moderator.py
│  ├─ scoring/
│  │  └─ rubric.py
│  ├─ runners/
│  │  ├─ debate_runner.py
│  │  ├─ pipeline_runner.py
│  │  └─ chat_mode_runner.py
│  └─ exporters/
│     └─ markdown_report.py
├─ skills/
│  └─ ...
├─ examples/
│  ├─ multimodal_research_idea.md
│  ├─ robotics_research_idea.md
│  ├─ wavelet_llm_manifold_idea.md
│  └─ sycophancy_affective_hallucination_research_brief.md
├─ docs/
│  ├─ prompt-contracts.md
│  ├─ reference/
│  │  └─ RLHF/
│  └─ plans/
│     └─ ...
└─ tests/
   └─ ...
```

## Quick Start

### 1) Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
```

### 2) Configure model access

```bash
cp .env.example .env
# 然后编辑 .env 填入你的真实 key
set -a && source .env && set +a
```

支持两类接口：
- GPT 兼容 responses：`$GPT_BASE_URL/responses`
- GLM 兼容 chat completions：`$GLM_BASE_URL`（支持根路径或完整端点）

GLM 官方文档接口：`https://open.bigmodel.cn/api/coding/paas/v4/chat/completions`

`GLM_BASE_URL` 支持两种写法：
- 根路径：`https://open.bigmodel.cn/api/coding/paas/v4`
- 完整端点：`https://open.bigmodel.cn/api/coding/paas/v4/chat/completions`

默认模型：
- Proposer: gpt-5.4
- Skeptic: glm-5.1
- Moderator: gpt-5.4

可选模型（已内置到 `configs/models.yaml`）：
- gpt-5.4
- glm-5.1

### 2.1) Configure Literature Retrieval (Unified Internal Provider)

ARC 的文献检索已统一为**单一路径**（pipeline/chat 共用）：
- Primary: arXiv（免费全文来源优先）
- Secondary: Semantic Scholar（免费元数据与 citation 排序增强）
- Supplement: DeepXiv web search（仅在前两者覆盖不足时补充，且限制在免费额度内）

关键配置文件：`configs/references.yaml`
- `search_pool_size` 默认 50（目标检索池）
- `final_reference_count` 默认 20（最终注入 prompts + 报告）

可选环境变量（见 `.env.example`）：
- `SEMANTIC_SCHOLAR_API_KEY`（可选，建议配置以提高稳定性）
- `DEEPXIV_TOKEN`（可选，建议配置）
- `ARC_DEEPXIV_ENABLED`（可选，默认 true）

DeepXiv 官方正常获取 token 流程（不绕过任何验证机制）：
1. 安装：`pip install deepxiv-sdk`
2. 触发官方注册/初始化：`deepxiv search "agentic memory" --limit 1`
3. 若出现邮箱验证、验证码或网页人工步骤，请在官方页面完成后，将 token 写入 `.env` 的 `DEEPXIV_TOKEN=...`

说明：ARC 不引入独立 MCP 编排路径；DeepXiv 仅作为 ARC 内部 provider 的第三优先补充源。

## Model Switcher (Terminal)

```bash
# 查看所有可用模型 + 当前角色绑定 + 配置就绪状态
arc models list

# 设置角色模型
arc models set proposer gpt-5.4
arc models set skeptic glm-5.1
arc models set moderator gpt-5.4
arc models set pipeline_writer gpt-5.4
arc models set pipeline_reviewer glm-5.1
arc models set pipeline_moderator gpt-5.4

# 诊断配置（离线）：检查 env 是否齐全
arc models doctor

# 在线烟雾测试：对当前角色模型逐个发起最小请求
arc models doctor --online

# 可选：提高慢模型稳定性
export ARC_LLM_TIMEOUT_SECONDS=180
export ARC_LLM_RETRY_ATTEMPTS=4

# GPT 思考深度（Responses API）
export ARC_GPT_REASONING_EFFORT=high
export ARC_GPT_VERBOSITY=medium
```

### 3) Run

```bash
arc run examples/multimodal_research_idea.md \
       --proposer gpt-5.4 \
         --skeptic glm-5.1 \
  --moderator gpt-5.4 \
       --gpt-effort high \
  --output-dir reports

# 若上次运行中断，可恢复
arc run examples/multimodal_research_idea.md \
       --proposer gpt-5.4 \
       --skeptic glm-5.1 \
       --moderator gpt-5.4 \
       --gpt-effort high \
       --output-dir reports \
       --resume
```

输出：
- `reports/<timestamp>/debate_log.jsonl`
- `reports/<timestamp>/final_state.json`
- `reports/<timestamp>/run_state.json`
- `reports/<timestamp>/research_decision_memo.md`

说明：每次运行都会创建新的时间戳目录，并更新 `reports/LATEST_RUN` 指向最近一次运行目录；`--resume` 会优先从该目录恢复。

### 3.1) Run Skill-First Pipeline (ARIS-style)

```bash
arc pipeline "multimodal agent safety benchmark" \
       --proposer gpt-5.4 \
       --skeptic glm-5.1 \
       --moderator gpt-5.4 \
       --gpt-effort high \
       --output-dir reports \
       --strict-gates

# 若上次 pipeline 中断，可恢复
arc pipeline "multimodal agent safety benchmark" \
       --proposer gpt-5.4 \
       --skeptic glm-5.1 \
       --moderator gpt-5.4 \
       --gpt-effort high \
       --output-dir reports \
       --checkpoint \
       --resume
```

Pipeline 主要产物（默认 `reports/<timestamp>/`）：
- `OUTPUT_INDEX.md`（统一解释每个输出文件，建议优先阅读）
- `pipeline_state.json`
- `TOPIC.txt`
- `REFERENCES.md`（统一 provider 输出：arXiv → Semantic Scholar → DeepXiv 补充）
- `LITERATURE_MAP.md`
- `IDEA_REPORT.md`
- `FINAL_PROPOSAL.md`
- `EVIDENCE_TABLE.md`
- `EXPERIMENT_PLAN.md`
- `RESEARCH_DECISION_MEMO.md`
- `AUTO_REVIEW.md`（当 stage chain 包含 `auto-review-loop` 时）

说明：当前 pipeline 为安全版，不会自动执行外部实验脚本；`experiment-bridge` 仅生成计划和脚本草案。
当启用 `--strict-gates`（默认）时，stage chain 必须包含 `novelty-check` 与 `debate-runner`。

可用以下命令快速解释某次运行目录中的文件用途：

```bash
arc explain-outputs --run-dir reports/<timestamp>
# 或默认解释 reports/LATEST_RUN 指向的最新一次运行
arc explain-outputs
```

### 3.2) Run Chat Mode (轻量头脑风暴)

如果你想做更轻松的角色扮演式讨论（不走严肃证明模板），可以使用独立的 chat mode：

```bash
arc chat-mode "multimodal hallucination mitigation for editing agents" \
       --proposer gpt-5.4 \
       --skeptic glm-5.1 \
       --moderator gpt-5.4 \
       --min-rounds-before-stop 20 \
       --max-rounds 0 \
       --export-best-consensus \
       --output-dir reports
```

特点：
- 至少进行 20 轮后，才允许裁判根据收敛/方案充分性判定停止
- `--max-rounds` 作为轮次数建议值（soft target），若裁判持续给出 `CONTINUE`，不会被该值强制截断
- 每轮三位 AI 都按聊天语气输出重点思路（创新 + 可行性）
- 每位 AI 单轮输出采用提示词建议长度（建议字数/段落），运行时不再强制截断
- 每次运行至少尝试检索 20 篇参考文献（含摘要）
- 裁判输出带结构化停机标记（CONTINUE / STOP_CONVERGED / STOP_PROPOSER_SUFFICIENT），并在未达到最少轮数时强制继续
- 一键导出 `BEST_CONSENSUS.md`（精简最优共识方案）
- 每轮写入详细时间戳（开始/三角色完成/轮次完成）
- 运行过程中实时更新 `CHAT_TRANSCRIPT.md`、`CHAT_MODE_INDEX.md`、`BEST_CONSENSUS.md`（interim 草稿），避免中断后无可读结论
- 每轮发言单独保存，便于阅读

恢复运行建议：
- 可使用 `--resume` 从 `chat_mode_state.json` 继续。
- `--resume` 要求 topic 与三角色模型映射一致；状态超过 24 小时会按新 run 处理。

Chat mode 主要产物（默认 `reports/<timestamp>/`）：
- `TOPIC_CHAT.txt`
- `REFERENCES.md`
- `CHAT_TRANSCRIPT.md`
- `BEST_CONSENSUS.md`
- `chat_mode_state.json`
- `CHAT_MODE_INDEX.md`
- `chat_rounds/round_01_proposer.md`
- `chat_rounds/round_01_skeptic.md`
- `chat_rounds/round_01_moderator.md`
- `chat_rounds/round_01.md`

文献流转说明（pipeline 与 chat 共用）：
- 统一 provider 先产出规范化引用对象：`source/id/year/citation_count/title/abstract/url`
- 这些对象会写入 `REFERENCES.md`（格式保持兼容）
- 下游 stage/chat 再消费同一份 `REFERENCES.md`，并继续生成：
       - `LITERATURE_MAP.md`
       - `FINAL_PROPOSAL.md`
       - chat mode 产物（`CHAT_TRANSCRIPT.md` / `BEST_CONSENSUS.md` 等）


### 4) Test

```bash
pytest -q
```

## Remote Repository Setup

如果你本地尚未关联远程仓库：

```bash
git init
git add .
git commit -m "feat: bootstrap ARC v0.1 debate engine"
git branch -M master
git remote add origin https://github.com/BUAAZhangHaonan/adversarial-research-copilot.git
git push -u origin master
```

## Roadmap

- Phase 1: Debate Engine (当前)
- Phase 2: Evidence Grounding (检索证据约束 Skeptic)
- Phase 3: Persistent Memory (跨任务复用经验)
- Phase 4: Minimal Experiment Planning
