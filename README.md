# Adversarial-Research-Copilot (ARC)

An adversarial multi-agent framework for iterative research idea critique, refinement, and convergence.

ARC 不是“自动做科研”的黑箱流水线，而是一个受控对抗式论证引擎：
- Proposer：把方案推到最强版本。
- Skeptic：系统性找漏洞并要求可验证证据。
- Moderator：只做结构化裁决和收敛判定。

## Why ARC

单模型自审容易陷入盲点。ARC 强制跨角色、跨模型对抗评审，让输出从“聊天记录”变成可落地的 Research Decision Memo。

## What We Borrowed (And Why)

基于对 ARIS 与 EvoScientist 的实仓审阅，ARC 在 v0.1.1 引入三项升级：
- 跨模型对抗约束：默认要求 Proposer 与 Skeptic 使用不同模型，避免同模自审盲点。
- 可恢复循环：每轮写入 `run_state.json`，支持 `--resume` 从中断点继续。
- 结构化裁决协议：Moderator 追加 machine-readable YAML，提升解析稳定性。

取舍：
- 借鉴 ARIS 的“轻量、可恢复、流程严控”。
- 吸收 EvoScientist 的“记忆与多阶段理念”。
- 暂不引入重框架编排，先把对抗收敛引擎打磨到可复用。

## Local References (Visible In Repo)

为便于对照学习，项目内提供本地参考仓库同步目录：
- `references/ARIS`
- `references/EvoScientist`

同步命令：

```bash
bash references/sync_references.sh
```

说明：参考仓库仅用于本地对照审阅，默认不纳入 ARC 仓库版本历史。

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

每轮固定协议：

Proposer 必须输出 6 块：
1. 核心命题
2. 方法机制
3. 为什么比已有思路强
4. 可验证实验
5. 最大风险
6. 备选方案

Skeptic 必须输出 6 块：
1. 最致命的问题
2. 隐含假设
3. 潜在伪创新点
4. 实验设计漏洞
5. 资源与实现风险
6. 只有通过什么证据我才会放行

Moderator 只输出 4 块：
1. scorecard
2. unresolved blockers
3. required revisions
4. continue_or_stop

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
│  ├─ models.yaml
│  └─ debate.yaml
├─ prompts/
│  ├─ proposer.md
│  ├─ skeptic.md
│  └─ moderator.md
├─ src/arc/
│  ├─ cli.py
│  ├─ orchestrator.py
│  ├─ state.py
│  ├─ schemas.py
│  ├─ memory.py
│  ├─ llm_client.py
│  ├─ agents/
│  │  ├─ proposer.py
│  │  ├─ skeptic.py
│  │  └─ moderator.py
│  ├─ scoring/
│  │  └─ rubric.py
│  ├─ runners/
│  │  └─ debate_runner.py
│  └─ exporters/
│     └─ markdown_report.py
├─ examples/
│  ├─ multimodal_research_idea.md
│  └─ robotics_research_idea.md
└─ tests/
   ├─ test_state.py
   ├─ test_rubric.py
   └─ test_convergence.py
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
- GLM 兼容 chat completions：`$GLM_BASE_URL/chat/completions`

GLM 官方文档接口：`https://open.bigmodel.cn/api/paas/v4/chat/completions`

默认模型：
- Proposer: gpt-5.4
- Skeptic: glm-5
- Moderator: gpt-5.4

可选模型（已内置到 `configs/models.yaml`）：
- gpt-5.4
- glm-5

## Model Switcher (Terminal)

```bash
# 查看所有可用模型 + 当前角色绑定 + 配置就绪状态
arc models list

# 设置角色模型
arc models set proposer gpt-5.4
arc models set skeptic glm-5
arc models set moderator gpt-5.4
arc models set pipeline_writer gpt-5.4
arc models set pipeline_reviewer glm-5
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
       --skeptic glm-5 \
  --moderator gpt-5.4 \
       --gpt-effort high \
  --output-dir reports

# 若上次运行中断，可恢复
arc run examples/multimodal_research_idea.md \
       --proposer gpt-5.4 \
       --skeptic glm-5 \
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
       --skeptic glm-5 \
       --moderator gpt-5.4 \
       --gpt-effort high \
       --output-dir reports \
       --strict-gates

# 若上次 pipeline 中断，可恢复
arc pipeline "multimodal agent safety benchmark" \
       --proposer gpt-5.4 \
       --skeptic glm-5 \
       --moderator gpt-5.4 \
       --gpt-effort high \
       --output-dir reports \
       --checkpoint \
       --resume
```

Pipeline 主要产物（默认 `reports/<timestamp>/`）：
- `pipeline_state.json`
- `LITERATURE_MAP.md`
- `IDEA_REPORT.md`
- `FINAL_PROPOSAL.md`
- `EVIDENCE_TABLE.md`
- `EXPERIMENT_PLAN.md`
- `RESEARCH_DECISION_MEMO.md`
- `AUTO_REVIEW.md`（当 stage chain 包含 `auto-review-loop` 时）

说明：当前 pipeline 为安全版，不会自动执行外部实验脚本；`experiment-bridge` 仅生成计划和脚本草案。
当启用 `--strict-gates`（默认）时，stage chain 必须包含 `novelty-check` 与 `debate-runner`。

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
