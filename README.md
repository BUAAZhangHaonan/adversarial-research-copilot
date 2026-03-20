# Adversarial-Research-Copilot (ARC)

An adversarial multi-agent framework for iterative research idea critique, refinement, and convergence.

ARC 不是“自动做科研”的黑箱流水线，而是一个受控对抗式论证引擎：
- Proposer：把方案推到最强版本。
- Skeptic：系统性找漏洞并要求可验证证据。
- Moderator：只做结构化裁决和收敛判定。

## Why ARC

单模型自审容易陷入盲点。ARC 强制跨角色、跨模型对抗评审，让输出从“聊天记录”变成可落地的 Research Decision Memo。

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
- Claude 兼容 chat completions：`$CLAUDE_BASE_URL/chat/completions`
- GPT 兼容 responses：`$GPT_BASE_URL/responses`

默认模型：
- Proposer: claude-sonnet-4-6
- Skeptic: gpt-5.4
- Moderator: gpt-5.4

### 3) Run

```bash
arc run examples/multimodal_research_idea.md \
  --proposer claude-sonnet-4-6 \
  --skeptic gpt-5.4 \
  --moderator gpt-5.4 \
  --output-dir reports
```

输出：
- `reports/latest/debate_log.jsonl`
- `reports/latest/final_state.json`
- `reports/latest/research_decision_memo.md`

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
