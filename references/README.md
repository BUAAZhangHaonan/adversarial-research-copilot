# Reference Repositories

Architecture references for ARC's pipeline redesign. Snapshots are committed to
the repo (embedded `.git` stripped, caches removed); heavy non-architecture
assets stay local-only via `.gitignore` exclusions.

| 目录 | 项目 | 对 ARC 的参考价值 | 上游 |
|---|---|---|---|
| `ARIS/` | ARIS (Auto-claude-code-research-in-sleep) | 轻量 skill 组织、可恢复循环、流程严控 | github.com/wanshuiyin/Auto-claude-code-research-in-sleep |
| `EvoScientist/` | EvoScientist | 记忆与多阶段理念 | github.com/EvoScientist/EvoScientist |
| `AI-Researcher/` | Stanford AI-Researcher | `src/filter_ideas.py` 的候选级定向查重操作（discover/duplicate-check 的原型） | github.com/NoviScl/AI-Researcher |
| `AI-Scientist/` | Sakana AI Scientist | 端到端分阶段流水线（idea→实验→写作→评审）；仓库只收 `ai_scientist/`、`review_ai_scientist/`、docs 与配置；`review_iclr_bench/`、`templates/`、`example_papers/`（约 190M LaTeX/示例产物）仅保留本地 | github.com/SakanaAI/AI-Scientist |
| `paper-qa/` | PaperQA2 | 检索/证据收集/引用追踪分层，"缺证据 vs 证据矛盾"的区分（审计 INSUFFICIENT_EVIDENCE 的原型）；`tests/`（28M fixtures）仅保留本地 | github.com/Future-House/paper-qa |
| `Co-Scientist/` | Co-Scientist（**非官方复刻**） | Google AI co-scientist 的多假设生成-锦标赛-演进架构。Google 无官方开源，本仓库为按论文（Gottweis et al., Nature 2026）实现的社区复刻，agent 编排/prompt/控制流遵循论文——参考其架构，勿当作官方实现 | github.com/Kaimen-Inc/Co-Scientist |

Refresh snapshots (dirs are tracked — re-running needs force):

```bash
bash references/sync_references.sh
```
