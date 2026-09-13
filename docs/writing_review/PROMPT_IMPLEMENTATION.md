# 写作提示词实施验证

2026-09-13，在 g203 的 master 上沿用用户给定修改包实施，未创建分支或修改外部 MCP。下文的 17/99 项结果是实施时的离线记录；后续真实成文、费用与最终 134 项回归见 [本轮交付](../WRITING_REVISION_20260913.md)。

## 已落实的资产

生产改动包括 18 份 discover/prestudy 现有提示词或报告模板、1 份新增短共同规范、manifest 中七项 system 装配。对应角色、任务 ID、工具集合、task_template、repair_template、tool_repair_template、read_progress_template 和 report 映射均保留。

完整写作指南保存为 [RESEARCH_WRITING_GUIDE.md](../RESEARCH_WRITING_GUIDE.md)，用户提供的 58 文件审阅与实际保留理由保存为 [PROMPT_WRITING_AUDIT.md](../PROMPT_WRITING_AUDIT.md)。两路编辑说明只用于本次开发验收，未注册生产角色。上述长指南和审阅文件不作为生产提示词依赖。

writer 的最低篇幅、段落和引用配额已移除；writing_limits 上限仍沿用输入。stage_summary、overview、candidate.text 按要点、必要背景、独立候选讨论分工。主文模板保留真实状态和来源链接，旧标题、撤回前提、修改和材料记录由技术页保存。

## 必要适配

研究员文件同时绑定 scout.SURVEY 和 scout.CHECK。包原文的共同结尾只要求 CandidateCheck；真实 schema 分别是 FieldBrief 与 CandidateCheck。通过现有 Jinja task_type 按任务选择对应段落，SURVEY 不再接收 CHECK 的交付指令，CHECK 也不接收调查对象指令。

writer 保留旧提示词的材料信任边界：输入中的文献、报告和命令不能改变角色职责。其余替换稿按用户提供文件覆盖；工具说明与历史完整卡提示词不变。

## 实际离线检查

命令：

```text
.venv/bin/python -m pytest -q tests/test_writing_prompt_contract.py
```

结果：17 passed（0.56 s）。使用真实 PromptLoader 与当前 Envelope / 研究 schema，验证七项 system 顺序和共同规范单次装入、既有工具与模板绑定、SURVEY/CHECK 返回对象、文档与双路编辑不进入生产、writer 修复时保留材料/身份/来源及科研条件、六份报告模板的严格 Jinja 渲染、单候选显示、暂停状态及历史内容位置。

另逐文件比较当前资产与 HEAD 原文：基线 58 份 Markdown 中 18 份替换、40 份未改；manifest 的实际差异仅为七项 system。该比较未使用哈希校验。read_paper 现有 DOI/URL/PDF、document_id 分页、find_text 和实际覆盖语义保留。

这些是提示词装配与模板检查，不能代表模型已用新提示词成文。保存材料的重写、真实费用与 A/B 文本核读由本次任务的独立验收材料记录。

## 相关回归检查

更新旧测试中绑定固定字数、旧标题、通用免责声明及禁止全部 common 文件的断言，改为检查当前写作规范、精确字段上限诊断、来源范围、真实状态及历史内容。完整对象不变、候选范围不变和历史输出原件不变的断言保留。长度修复行为从实际 Markdown 修复消息验证，Python 诊断只要求精确字段、数量和上限。

回归发现并修复两处模板问题：待预研总览原替换稿没有显示已登记的候选关系；技术稿在新旧核心认识相同时重复打印该认识。现在前者继续展示真实关系，后者在历史章节注明认识未变，并保留原动机和修改记录。

```text
.venv/bin/python -m pytest -q tests/test_prompts.py tests/test_polishing.py tests/test_discovery_reports.py tests/test_discovery_current_prompt.py tests/test_writing_prompt_contract.py --tb=short
```

结果：99 passed（5.72 s）。这包含上述 17 例新装配检查；没有启动真实 API 调用。
