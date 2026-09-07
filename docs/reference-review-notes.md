# 参考项目与本版 ARC 的取舍

ARC 的目标是抽取值得研究的 idea，说明依据、知识增量和可行性。实验执行与论文写作由人完成。下面比较的是隔离目录中保存的参考源码与任务书 §2.3、附录 C，不把上游宣传、自动评分或其他领域结果当作 ARC 的性能证明。

## 六个已核对的参考项目

| 项目与源码位置 | 项目目标与可借鉴思想 | 本版实际采用及范围 |
|---|---|---|
| [ARIS](../references/ARIS/skills/idea-discovery/SKILL.md)（Auto-claude-code-research-in-sleep） | 用 Markdown skills 组织文献调查、idea生成、核查、批评和方案展开；idea-discovery 在方法展开前固定 Problem Anchor。其整体流程还包含 pilot、实验和写作。 | 固定问题锚点、分阶段交付、Markdown提示词与可恢复任务。真正转向只生成冻结建议；不采用自动pilot、论文写作或反复生成直到挑出满意idea的流程。 |
| [Stanford AI-Researcher](../references/AI-Researcher/ai_researcher/src/filter_ideas.py) | 面向研究提案生成与人类研究评估；filter_ideas 对具体提案重新检索，并逐篇比较研究问题和方法是否相同。 | 对每张卡核查最近工作，记录具体覆盖关系、适用条件和证据。访问失败作为未完成核查，不直接判定重复；不照搬其NLP任务偏好或二元打分筛选。 |
| [Sakana AI-Scientist](../references/AI-Scientist/ai_scientist/generate_ideas.py) | 面向从idea到实验、写作与评审的自动科研；生成器读取 experiment.py 和历史idea档案，迭代候选。 | 保留候选历史，分开生成与判断，通过档案比较防止换词重复。ARC不要求从固定实验代码模板提出问题，不执行科研实验，也不把自评分当真值。 |
| [PaperQA2](../references/paper-qa/src/paperqa/agents/tools.py)（paper-qa） | 面向科学文献问答；PaperSearch、GatherEvidence、GenerateAnswer 分开处理论文发现、问题证据与回答。 | 区分搜索、原文读取、问题级证据和报告；登记来源、摘录与定位，区分原文、metadata和二级分析。未引入整套PaperQA平台，也不把文献问答能力等同于idea质量。 |
| [EvoScientist](../references/EvoScientist/EvoScientist/middleware/memory.py) | 面向持续协作的科研agent；记忆中间件抽取并保存用户资料、偏好和实验结论，向后续会话注入记忆。 | 跨阶段保留研究事实、资源条件、历史结果和未决争点，使用不可变卡版本与明确证据依赖。没有采用自动学习用户学术品味或通用多团队执行框架。 |
| [Co-Scientist](../references/Co-Scientist/README.md)（Kaimen-Inc 非官方复刻） | 从研究目标生成多个假设，经过反思、Elo排序、演进与近邻比较形成研究总览；README明确不隶属Google或论文作者。 | 借鉴多个竞争解释并存、比较知识增量、根据新证据调整。未采用Elo锦标赛、向量库或整套Supervisor/多角色框架；不能称作Google官方实现。 |

## 本版实际落点

- `discover`、`develop`、`run` 默认分别停止；只有开发验收入口显式授权串联。抽卡最多五次，共享原始调查，每次聚焦一个问题族和一张核心卡。
- SQLite保存卡版本、证据、issue、任务和人民币预算；Markdown报告可从状态重建。角色使用严格JSON信封和登记的Markdown提示词，通过统一模型与工具adapter调用。旧run_state.json主状态、moderator YAML协议、pipeline/chat入口不再是本版设计。
- ARC直接调用仅DeepSeek V4 Flash/Pro，全部max，阶段及开发父预算约束所有调用。角色分工不构成独立科学验证；参考项目的多provider能力和跨模型效果声明不属于本版已实现或已验证的能力。

这些是有限的设计取舍，不是整套参考框架的移植。当前工程与真实验收状态以 [IMPLEMENTATION_AUDIT](IMPLEMENTATION_AUDIT.md) 和 [E2E_REPORT](E2E_REPORT.md) 为准。
