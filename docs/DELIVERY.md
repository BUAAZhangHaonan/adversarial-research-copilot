# ARC 项目交付说明

本文是6a350bc时点的历史交付记录；当前master归并、发布及未完成项见[MASTER_STATUS.md](MASTER_STATUS.md)。

ARC已按任务书重构为研究idea抽卡、方案展开与可行性压力测试工具。实现位于g203隔离分支；实验执行和论文写作由人完成。工程验证通过；最终保存状态显示L2入口执行完成1/3，L3：E2E记录为stopped_at_develop，selected_card=card_52bce58017164c2b9594c418eb0cac7b；未记录完整自然同卡链。执行完成不等于idea得到科学认可。

## 实现与位置

- 隔离目录：`/home/g203/zhanghaonan/arc-vnext-20260907`。
- 分支：`codex/arc-vnext-20260907`。原项目master与历史材料保留，未推送或合并。
- 已测代码提交：`a14da30f31a1541b9a5732c6aa3b85ab9dc689f9`；本说明生成时文档HEAD：`a14da30f31a1541b9a5732c6aa3b85ab9dc689f9`。交付包最终HEAD以MANIFEST.json为准。
- 三入口默认分阶段停止；保留明确问题输入、不可变卡版本、主张/争点、来源核查、最多五次探索及冻结转向建议。
- 27份Markdown提示词资产、严格结果协议、SQLite状态与费用账本、中文档案检索、可重建中文报告。
- 仅DeepSeek V4 Flash/Pro，所有语义调用max；384000输出上限。阶段默认20元，本次明确批准的三个暂停账户各追加5元至25元；开发父预算仍为100元。

逐条代码、测试和真实证据映射：[实现审计](IMPLEMENTATION_AUDIT.md) · [执行清单](IMPLEMENTATION_CHECKLIST.md)。
六个参考项目的取舍：[参考比较](reference-review-notes.md)。使用与变更说明：[README](../README.md) · [迁移](MIGRATION.md)。

## 实际验证

| 层级 | 结果 |
|---|---|
| L1工程 | 342项测试通过（65.59s）；从已测提交构建wheel/sdist，独立安装后在仓库外验证CLI、资源及schemas源码hash。 |
| L2实际接口与入口 | Flash/Pro JSON+native tools+max联合探针通过；真实读取、保存响应零新增调用恢复通过。discover: COMPLETED×1, PAUSED_PROTOCOL×3；develop: PAUSED_PROTOCOL×3；run: PAUSED_PROTOCOL×3 |
| L3自然同卡链 | E2E记录为stopped_at_develop，selected_card=card_52bce58017164c2b9594c418eb0cac7b；未记录完整自然同卡链；人工输入L2不计入自然同卡链。 |
| L4固定材料 | 已保存3个对照结果，其中0个自动对照完成。其余保留未完成；自动评价不能证明ARC质量改善。 |
| SSH与报告 | 独立ARC进程跨启动SSH退出继续工作；真实报告重建不改研究状态。旧日期恢复有工程测试，未宣称真实等待24小时或强制网络断流验证。 |

### 最终状态与科研结论

COMPLETED只表示该入口执行结束。assessment单独保留；REJECTED或NEEDS_EVIDENCE不应改写成技术失败。

| 运行 | 输入类别 | 执行状态 | assessment | 停止原因 |
|---|---|---|---|---|
| ARC_VNEXT_VALIDATION.discover | 研究阶段；L3另核E2E | PAUSED_PROTOCOL | 未记录 | TASK_DEPENDENCY_CHANGED_FORK_REQUIRED |
| ARC_VNEXT_VALIDATION_V2.discover | 研究阶段；L3另核E2E | PAUSED_PROTOCOL | 未记录 | excerpt_not_in_returned_source |
| ARC_VNEXT_VALIDATION_V3.discover | 研究阶段；L3另核E2E | PAUSED_PROTOCOL | 未记录 | INVALID_OUTPUT_AFTER_REPAIR |
| explicit_input.develop | 明确人工输入，仅L2 | PAUSED_PROTOCOL | 未记录 | TASK_DEPENDENCY_CHANGED_FORK_REQUIRED |
| explicit_input.run | 明确人工输入，仅L2 | PAUSED_PROTOCOL | 未记录 | metadata_source_empty_read_loop_development_pause |
| ARC_RENDERING_VALIDATION.discover | 研究阶段；L3另核E2E | COMPLETED | 未记录 | no_distinct_direction |
| ARC_RENDERING_VALIDATION.develop | 研究阶段；L3另核E2E | PAUSED_PROTOCOL | 未记录 | TOOL_ARGUMENTS_INVALID |
| explicit_input_schema_v2.run | 明确人工输入，仅L2 | PAUSED_PROTOCOL | 未记录 | INVALID_OUTPUT_AFTER_REPAIR |
| explicit_input_schema_v2.develop | 明确人工输入，仅L2 | PAUSED_PROTOCOL | 未记录 | AFFECTED_CLAIMS_COVERAGE |
| explicit_input_schema_v3.run | 明确人工输入，仅L2 | PAUSED_PROTOCOL | 未记录 | TOOL_ARGUMENTS_INVALID |

E2E_RESULT原记录：`{"L2": {"discover": "COMPLETED", "develop": "PAUSED_PROTOCOL"}, "L3": "stopped_at_develop", "selected_card": {"card_id": "card_52bce58017164c2b9594c418eb0cac7b", "version": 1, "selection_method": "explicit_development_first_retained"}, "assessment": null}`。

批准续跑及新schema入口的驱动记录：
- approved-continuation / natural_rendering：{"L2": {"discover": "COMPLETED", "develop": "PAUSED_PROTOCOL"}, "L3": "stopped_at_develop", "selected_card": {"card_id": "card_52bce58017164c2b9594c418eb0cac7b", "version": 1, "selection_method": "explicit_development_first_retained"}, "assessment": null}。
- approved-continuation / explicit_develop：{"status": "PAUSED_PROTOCOL", "assessment": null, "stop_reason": "TASK_DEPENDENCY_CHANGED_FORK_REQUIRED"}。
- approved-continuation / segmentation_direct_pro：{"comparison_status": "incomplete"}。
- l2-schema-fork / run：{"status": "PAUSED_PROTOCOL", "assessment": null, "reason": "INVALID_OUTPUT_AFTER_REPAIR"}。
- l2-schema-fork / develop：{"status": "PAUSED_PROTOCOL", "assessment": null, "reason": "AFFECTED_CLAIMS_COVERAGE"}。
- l2-schema-fork / run：{"status": "PAUSED_PROTOCOL", "assessment": null, "reason": "TOOL_ARGUMENTS_INVALID"}。

驱动异常不等于科研否决；同一run以最终VALIDATION_SNAPSHOT为准，较早驱动结果保留为执行记录。SKIPPED_ALREADY_COVERED本身不算完成，只有其指向run的实际COMPLETED状态才计入。

完整结果及原件指针：[真实验收记录](E2E_REPORT.md) · [固定材料对照](L4_REPORT.md) · [原文复核](RENDERING_EVIDENCE_REVIEW.md)。

本次保留的自然研究卡及边界：[自然发现结果](NATURAL_DISCOVERY_RESULT.md)；同卡develop停点：[工具参数审计](NATURAL_DEVELOP_PROTOCOL_REVIEW.md)。

真实定向补证与具体主张的关系见[补证审计](REAL_TARGETED_RETRIEVAL_REVIEW.md)；最后两处协议说明修复及安装验证见[契约修复](RESOURCE_SCHEMA_FIX.md)。

最终已测提交上的run实际验证停点见[最终工具参数审计](FINAL_RUN_PROTOCOL_REVIEW.md)。工程修复通过测试与安装检查，尚未获得该入口完成的真实验收。

对照专项审阅：[direct-Pro原文核查](L4_DIRECT_PRO_EVIDENCE_REVIEW.md) · [渲染协议失败](L4_RENDERING_PROTOCOL_REVIEW.md) · [留出任务归属检查](L4_HOLDOUT_PROTOCOL_REVIEW.md)。

## 费用与当前限制

唯一开发父账户`arc-vnext-validation-20260907`：已结算估计 **45.154048–45.303543元**；预留0.000000元，未知调用0，可准入剩余54.696457元。这不是供应商发票。分项见[费用报告](COST_REPORT.md)。

完整输出预留使单次Pro准入上界为15.912元。因此一个20元阶段即使只花了约4.21元，也可能无法准入下一请求。用户已明确批准三个已暂停账户各追加5元，并在同一账本继续；正式默认与父级100元上限保持原值。[追加授权记录](BUDGET_EXTENSION_AUTHORIZATION.md)列出精确范围。接口空正文、格式修复失败与科学上的不值得做分开记录。

新颖性、引文条件和可辨识性仍需研究者复核；准确摘录不保证复合主张或外推正确。部分卡的原文复核已发现条件遗漏及推断过度，保留在审计中，没有人工篡改模型判断以求通过。

## 交付内容

交付包包含说明、逐条审计、成本与验收报告、研究卡视图、wheel/sdist和本地Git bundle；MANIFEST.json记录文件SHA256。完整数据库、原始消息、工具返回和文献位于g203隔离目录的私有`.arc-validation/`中，不进入交付包或Git。
bundle需要原基线`3bc93dd0be54d3c2ffc4c2b4f9f2014c79064c85`；g203隔离worktree是已验证源码位置。实验、训练、论文、服务修改、发布及主分支合并均未执行。
