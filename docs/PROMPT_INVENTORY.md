# 当前提示词清单

本轮按[功能重构要求](FUNCTIONAL_REDESIGN_REQUEST.md)重写科学职责与校准例子。原始提示词保存在 tests/fixtures/prompts_pre_redesign，仅供明确的历史审核消融使用；当前资产不再声称与上一版附录逐字相同。

默认 discover 使用 discovery.CONCEIVE 和 scientific_reviewer.INVOKE，必要时调用 discovery.REVISE。调查按材料需要触发。develop 展开后使用同一科学审查，run 独立审查；proposer/skeptic/moderator 只恢复已有旧任务，不是新默认链。

| 已登记 prompt_id | 工具上限 |
| --- | --- |
| investigator.INVOKE | read_paper, read_record, read_web, request_capability, search_literature, search_web |
| investigator.SCOPE_AUDIT | read_paper, read_record, read_web, request_capability, search_literature, search_web |
| librarian.INVOKE | lookup_archive, read_record, request_capability |
| discovery.FRAME | lookup_archive, read_paper, read_record, read_web, search_literature, search_web, request_capability |
| discovery.NEXT_DRAW | lookup_archive, read_paper, read_record, read_web, search_literature, search_web, request_capability |
| discovery.COMPOSE | lookup_archive, read_paper, read_record, read_web, search_literature, search_web, request_capability |
| novelty_examiner.INVOKE | read_paper, read_record, read_web, search_literature, search_web, request_capability |
| selector.INVOKE | read_paper, read_record, read_web, search_literature, search_web, request_capability |
| developer.INVOKE | read_paper, read_record, read_web, request_capability, search_literature, search_web |
| proposer.INVOKE | read_paper, read_record, read_web, search_literature, search_web, request_capability |
| skeptic.INVOKE | read_paper, read_record, read_web, search_literature, search_web, request_capability |
| moderator.INVOKE | read_paper, read_record, read_web, search_literature, search_web, request_capability |
| reporter.INVOKE |  |
| evaluator.INVOKE |  |
| developer.IMPORT | read_paper, read_record, read_web, request_capability, search_literature, search_web |
| discovery.CONCEIVE | lookup_archive, read_paper, read_record, read_web, search_literature, search_web, request_capability |
| discovery.REVISE | lookup_archive, read_paper, read_record, read_web, search_literature, search_web, request_capability |
| scientific_reviewer.INVOKE | lookup_archive, read_paper, read_record, read_web, search_literature, search_web, request_capability |

所有科学行为说明、校准例子、工具说明集中在注册 Markdown；JSON Schema 负责字段形状，代码负责状态与额度。运行时只开放已安装且费用可核查的工具子集。

每个任务保存实际渲染输入、响应和工具记录，恢复成功任务不重新生成。结构纠正继续使用原快照；工具参数与最终 JSON 分别只有一次纠正额度。科学错误由定向修订和独立复核处理，不由格式修复改写研究结论。

reporter 提示词已登记，但报告由 reports.py 确定性构建。修改 reporter.md 不会自动改变报告路径；本轮同时修改了报告代码和模板。主报告只呈现当前卡及当前版本的科学结论，检索命中放 SEARCH_SOURCES.md。

验证覆盖注册资源、模板输入隔离、缺资源/变量、工具子集、结构修复、快照恢复与异目录安装。AST 边界防止新增内联科学提示词；这些检查不证明模型具备科研品味。真实结果见 FUNCTIONAL_REDESIGN.md。
