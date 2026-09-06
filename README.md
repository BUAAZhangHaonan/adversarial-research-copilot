# Adversarial-Research-Copilot (ARC)

**从文献中勘探新问题，用对抗辩论压力测试你的 idea。**

ARC (v0.1.0) 是一台双引擎的科研论证机器，而不是"自动做科研"的黑箱流水线：

- **discover（勘探引擎）**：不带着 idea 来，而是先宽检索、深阅读，从文献的矛盾与空白中挖出**问题本身是新的**研究方向——痛点已饱和的方向会被审计杀掉，A+B 式增量创新过不了品味门。
- **develop / debate（方案引擎）**：Proposer 把方案推到最强，Skeptic 系统性找漏洞，Moderator 只做结构化裁决——把一个已有 idea 打磨成可落地的 Research Decision Memo。

核心信念：单模型自审容易陷入盲点，单方向精修只能把烂想法打磨光亮。先勘探，再对抗，输出才可能是"别人没做过、且值得做"的问题。

## Why ARC

1. **方向优先于方案。** 好的切入点在调研文献时就能找到——互相矛盾的结论、被反复提及却无人解决的局限、活跃方向的无人交叉点。discover 模式就是把这个过程工程化。
2. **反增量护栏。** 品味门显式检测三类坏味道：A+B 方法重组、"先箭后靶"（先有方法再找问题）、痛点饱和（基准已 98%+ 还在刷分）。硬规则：方法重组而无新问题，直接 KILL。
3. **跨模型对抗。** 默认 deepseek-v4-flash 负责生成、deepseek-v4-pro 负责裁决，避免同一个大脑自我博弈。
4. **可恢复、可审计。** 每轮/每个 stage 落盘状态，`--resume` 从中断点继续；所有产物有 OUTPUT_INDEX 索引。

## Two Engines

```text
[discover: 勘探引擎]                          [debate/chat: 压力测试引擎]

 粗糙领域描述                                  User Research Idea
      |                                             |
      v                                             v
 theme-framing (flash)                        Problem Framer
      |                                             |
      v                                             v
 ScholarTrace 宽检索+重排 (MCP)               Shared Research State
      |                                        +-------------+
      v                                        v             |
 ScholarAnalysis 全文深读 (MCP)           Proposer        Skeptic
      |                                        |             |
      v                                        +------+------+
 gap-mining 四类空白 (pro)                          v
      |                                        Moderator
      v                                   (scorecard/blockers/
 webresearch 痛点审计 (MCP + pro)           revisions/stop)
      |                                        |
      v                              Continue Loop <--> Converged Memo
 idea-portfolio (flash)
      |
      v
 taste-gate 品味门 (pro)
      |
      v
 DISCOVERY_REPORT.md --[--stress-test]--> develop 辩论
```

## What We Borrowed (And Why)

基于对 ARIS 与 EvoScientist 的实仓审阅，ARC 在 v0.1.0 版本收敛出三项升级：
- 跨模型对抗约束：支持启用 Proposer 与 Skeptic 的跨模型对抗；当前默认配置不强制 Proposer 与 Skeptic 使用不同模型，但可在 `configs/debate.yaml` 中开启。
- 可恢复循环：每轮写入 `run_state.json`，支持 `--resume` 从中断点继续。
- 结构化裁决协议：Moderator 追加 machine-readable YAML，提升解析稳定性。

取舍：
- 借鉴 ARIS 的"轻量、可恢复、流程严控"。
- 吸收 EvoScientist 的"记忆与多阶段理念"。
- 暂不引入重框架编排，先把对抗收敛引擎打磨到可复用。

## Local References (Visible In Repo)

为便于对照学习，项目内提供本地参考仓库同步目录（可随时更新）：
- `references/ARIS`
- `references/EvoScientist`

```bash
bash references/sync_references.sh
```

说明：`references/*` 主要用于本地对照审阅；`docs/reference/*` 作为项目文献资产可随仓库版本管理。

## Skills Library

ARC 已提供一套技能化工作流（见 `skills/`），供 pipeline 模式使用：
`research-lit` / `idea-creator` / `novelty-check` / `research-refine` / `experiment-bridge` / `debate-runner` / `auto-review-loop` / `memo-synthesis` / `evidence-grounding` / `pipeline-arc`

这套库借鉴 ARIS 的轻量技能组织方式，但围绕 ARC 的 Proposer/Skeptic/Moderator 对抗收敛逻辑重写。

## Prompt Contracts

所有角色提示词采用"人类可读分析 + 固定 YAML 尾部"协议：人类可读部分允许灵活组织，但机器可读字段名是**运行时与提示词之间的稳定契约**（如 Moderator 的 `scorecard`/`continue_or_stop`，develop 的 `[JUDGE_DECISION]:` 标记，discover 的 `gaps`/`judgments` 等）。改提示词必须同步改契约测试，详见 `docs/prompt-contracts.md` 与 `tests/test_prompts.py`。

## Debate Protocol

- Proposer：主张一个首选方案，回应上一轮 blocker / revision，结尾输出 `proposal_quality`、`top_next_actions`、`open_questions`。
- Skeptic：聚焦最致命风险、证据缺口与必须回答的问题，结尾输出 `risk_summary`、`next_round_focus`、`evidence_to_collect`。
- Moderator：给出整体裁决、`scorecard`、`unresolved_blockers`、`required_revisions` 与 `continue_or_stop`。

## Convergence Rules

默认停止条件（debate 模式）：
- 连续 2 轮无未解决 blocker。
- 平均分 >= 4.0。
- 至少完成 2 轮。
- 或 Moderator 显式给出 STOP。

develop 模式的收敛：moderator 输出 `[JUDGE_DECISION]: CONTINUE | STOP_CONVERGED | STOP_PROPOSER_SUFFICIENT`，未达最少轮数时强制继续；`max_rounds` 是跨评审周期的**总轮数硬上限**（默认 60，0 = 不限）。

## Project Structure

```text
adversarial-research-copilot/
├─ README.md / LICENSE / pyproject.toml / .env.example
├─ configs/
│  ├─ develop.yaml            # develop 模式参数（轮数/评审周期/上下文滑窗）
│  ├─ discover.yaml           # discover 模式参数（池深/深读数/idea 数）
│  ├─ models.yaml             # 模型注册表 + 角色默认
│  ├─ runtime_models.yaml     # 当前角色绑定（arc models set 持久化于此）
│  ├─ references.yaml         # 内置文献检索（chat/pipeline 用）
│  └─ debate.yaml             # 辩论收敛参数
├─ prompts/latest/
│  ├─ default/                # 严肃辩论角色（en/zh + 无后缀）
│  ├─ chat/                   # chat 模式角色 + reviewer + drift monitor
│  └─ discover/               # discover 五角色（theme_framer/gap_miner/
│  │                          #   saturation_auditor/idea_generator/taste_judge）
├─ src/arc/
│  ├─ cli.py                  # arc 入口（run=pipeline=develop/discover/...）
│  ├─ orchestrator.py         # 辩论主循环
│  ├─ llm_client.py           # 双端点 LLM 客户端（重试/流式降级）
│  ├─ model_registry.py       # 角色-模型绑定
│  ├─ skill_engine.py         # SKILL.md 加载与 stage chain 解析
│  ├─ state.py / schemas.py / memory.py / run_paths.py / prompting.py / topic_refiner.py
│  ├─ agents/                 # proposer / skeptic / moderator / reviewer / drift_monitor
│  ├─ providers/
│  │  ├─ literature.py        # 内置文献 provider（arXiv→S2→DeepXiv）
│  │  └─ mcp_bridge.py        # MCP 桥接（stdio + SSE 客户端 + 硬失败健康检查）
│  ├─ runners/
│  │  ├─ debate_runner.py     # arc run
│  │  ├─ pipeline_runner.py   # arc pipeline（9 阶段 skill-first）
│  │  ├─ develop_runner.py    # arc develop（嵌套评审周期）
│  │  └─ discover_runner.py   # arc discover（7 阶段文献勘探）
│  ├─ scoring/rubric.py       # YAML 解析 + 收敛判定
│  └─ exporters/markdown_report.py
├─ skills/                    # 技能库（pipeline stage 定义）
├─ examples/                  # 示例研究 brief
├─ docs/
│  ├─ prompt-contracts.md     # 提示词契约文档
│  └─ plans/                  # 历史修复计划
└─ tests/                     # 65 个测试（含 prompt 契约 / MCP 桥 / runner）
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

默认模型（DeepSeek 分工：flash 生成 / pro 裁决，OpenAI 兼容端点）：
- Proposer / Skeptic / pipeline_writer: `deepseek-v4-flash`
- Moderator / pipeline_reviewer / pipeline_moderator: `deepseek-v4-pro`

```dotenv
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=your_key
```

可选模型（保留条目，需自备有效 key）：`gpt-5.4`、`glm-5.1`（GPT 兼容 responses / GLM 兼容 chat completions，详见 `.env.example`）。

### 2.1) Configure Literature Retrieval（chat/pipeline 内置路径）

develop 与 pipeline 使用内置统一 provider（与 discover 的 MCP 路径相互独立）：
- Primary: arXiv → Secondary: Semantic Scholar → Supplement: DeepXiv web（限额内）

关键配置：`configs/references.yaml`（`search_pool_size` 50 / `final_reference_count` 20）。可选环境变量见 `.env.example`（`SEMANTIC_SCHOLAR_API_KEY`、`DEEPXIV_TOKEN` 等）。

### 2.2) Configure MCP Services（discover 模式必需）

discover 依赖三个本地 MCP 服务，**任一不可用直接报错停止，不降级**（服务端各自使用自己的 API key，不消耗你的 DeepSeek 配额）：

| 服务 | 传输 | 启动 |
|---|---|---|
| ScholarTrace | SSE `http://127.0.0.1:8001/sse` | `bash /home/g203/zhanghaonan/ScholarTrace/run_scholartrace_mcp_sse.sh` |
| ScholarAnalysis | SSE `http://127.0.0.1:8005/sse` | `bash /home/g203/zhanghaonan/ScholarAnalysis/run.sh` |
| webresearch-mcp | stdio 子进程 | `/home/g203/zhanghaonan/webresearch-mcp/.venv/bin/python -m webresearch_mcp.server` |

在 `.env` 中配置（token 为本地文件，绝不入库）：

```dotenv
ARC_MCP_WEBRESEARCH_CMD="/home/g203/zhanghaonan/webresearch-mcp/.venv/bin/python -m webresearch_mcp.server"
ARC_SCHOLARTRACE_URL=http://127.0.0.1:8001/sse
ARC_SCHOLARTRACE_TOKEN=...
ARC_SCHOLARANALYSIS_URL=http://127.0.0.1:8005/sse
ARC_SCHOLARANALYSIS_TOKEN=...
```

注意：服务监听 `0.0.0.0`，但本机请用 `127.0.0.1` 连接（访问自身外部 IP 会挂起）。

### 3) Run

#### 3.0) arc discover —— 从文献中挖新问题（先跑这个）

```bash
arc discover "memory architectures for LLM agents: what breaks after 100 turns" \
       --papers 60 --deep-read 12 --ideas 8 \
       --output-dir reports
# 中断后可 --resume；加 --stress-test 自动把 top KEEP 送入 develop 辩论
```

七阶段：theme-framing → ScholarTrace 宽检索 → ScholarAnalysis 深读 → gap-mining（矛盾/反复局限/无人交叉点/过时前提）→ webresearch 痛点审计（杀饱和方向）→ idea-portfolio（问题必须新，实现允许简单）→ taste-gate 品味门。

产物（`reports/<ts>_flash_pro/`）：`DISCOVERY_REPORT.md`（先读）、`THEME.md`、`CANDIDATE_POOL.md`、`DEEP_READ/`、`GAP_ANALYSIS.md`、`SATURATION_AUDIT.md`、`IDEA_PORTFOLIO.md`、`OUTPUT_INDEX.md`。

审计全灭是合法结果：报告会解释每个方向为何被杀，并建议放宽 `--papers`/`--deep-read` 或换领域。

#### 3.1) arc run —— 严肃辩论

```bash
arc run examples/multimodal_research_idea.md \
       --proposer deepseek-v4-flash \
       --skeptic deepseek-v4-flash \
       --moderator deepseek-v4-pro \
       --output-dir reports [--resume]
```

输出：`debate_log.jsonl` / `final_state.json` / `run_state.json` / `research_decision_memo.md`。每次运行创建时间戳目录并更新 `reports/LATEST_RUN`；`--resume` 优先从该目录恢复。

#### 3.2) arc pipeline —— ARIS 风格九阶段流水线

```bash
arc pipeline "multimodal agent safety benchmark" \
       --proposer deepseek-v4-flash \
       --skeptic deepseek-v4-flash \
       --moderator deepseek-v4-pro \
       --output-dir reports --strict-gates [--checkpoint] [--resume]
```

产物：`OUTPUT_INDEX.md`（建议优先阅读）、`REFERENCES.md`、`LITERATURE_MAP.md`、`IDEA_REPORT.md`、`FINAL_PROPOSAL.md`、`EVIDENCE_TABLE.md`、`EXPERIMENT_PLAN.md`、`RESEARCH_DECISION_MEMO.md`、`AUTO_REVIEW.md`。安全版：不自动执行外部实验脚本；`--strict-gates`（默认）要求 stage chain 包含 `novelty-check` 与 `debate-runner`。

#### 3.3) arc develop —— 快速发展（嵌套评审周期，原 chat-mode）

```bash
arc chat-mode "multimodal hallucination mitigation for editing agents" \
       --proposer deepseek-v4-flash \
       --skeptic deepseek-v4-flash \
       --moderator deepseek-v4-pro \
       --min-rounds-before-stop 2 --max-rounds 60 \
       --export-best-consensus \
       --output-dir reports [--resume]
```

特点：外层 Reviewer 评审周期 × 内层三角色聊天辩论；Drift Monitor 防跑题；轮次级重试（单次瞬时故障不再杀死数小时运行）；上下文滑窗控制 prompt 增长；`DEVELOP_TRANSCRIPT.md` / `BEST_CONSENSUS.md` 实时更新。循环上限等参数以 `configs/chat_mode.yaml` 为准（CLI 未传时）。

#### 3.4) 辅助命令

```bash
arc refine-topic "raw problem"          # writer/reviewer 迭代打磨选题，可 --run-pipeline-after
arc explain-outputs [--run-dir DIR]     # 解释某次运行目录中每个产物的用途
```

### 4) Test

```bash
pytest -q
```

## Model Switcher (Terminal)

```bash
arc models list                          # 模型注册表 + 角色绑定 + 就绪状态
arc models set skeptic deepseek-v4-pro   # 例：把 Skeptic 升级为 pro
arc models doctor                        # 离线诊断 env
arc models doctor --online               # 在线冒烟（逐角色最小请求）

# 可选：稳定性与生成控制
export ARC_LLM_TIMEOUT_SECONDS=180
export ARC_LLM_RETRY_ATTEMPTS=4
export ARC_MCP_CALL_TIMEOUT_SECONDS=900  # scholartrace.query 可能要几分钟
```

## Remote Repository Setup

```bash
git init && git add . && git commit -m "feat: bootstrap ARC v0.1 debate engine"
git branch -M master
git remote add origin git@github.com:BUAAZhangHaonan/adversarial-research-copilot.git
git push -u origin master
```

本机注意：22 端口不通且 HTTPS 凭证属于其他账号时，走 SSH over 443：
`git remote set-url origin ssh://git@ssh.github.com:443/BUAAZhangHaonan/adversarial-research-copilot.git`

`.env` 已被 `.gitignore` 忽略——**API key 只存在于本地**。

## Roadmap

- Phase 1: Debate Engine（已完成）——辩论收敛 + chat mode + pipeline
- Phase 2: Discovery Engine（当前）——discover 模式已上线：文献勘探 + 痛点审计 + 品味门；下一步：提示词打磨模块（`arc prompts optimize`，用 LLM 迭代优化各角色提示词）
- Phase 3: Evidence Grounding（检索证据直接约束 Skeptic 的攻击面）
- Phase 4: Persistent Memory（跨任务复用勘探与辩论经验）
- Phase 5: Minimal Experiment Planning（实验桥接到执行）
