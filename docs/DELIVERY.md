# ARC 当前交付说明

ARC 的范围是研究 idea 抽卡、方案展开与可行性压力测试。实验执行和论文写作由人完成；PROMISING 只表示值得继续调查。当前源码在 g203 `/home/g203/zhanghaonan/adversarial-research-copilot`，只维护并推送 master。

## 实现与验证

- 三个独立入口 discover/develop/run，各阶段默认结束即停；最多五次发现机会、不可变卡版本、主张与争点、来源登记、预算与恢复、中文档案和报告均保留。
- 仅 DeepSeek V4 Flash/Pro，语义调用 max、完整输出上限 384000；默认每阶段20元。本次开发沿用原100元父账本，追加范围见[授权记录](BUDGET_EXTENSION_AUTHORIZATION.md)。
- 工具读取上限64000字符；工具参数与最终JSON各有一次纠错。正文或条件改变后机械递增漏填版本，移除旧版本证据引用，再让Agent重新取证。
- 协议失败可由用户显式创建任务新版本，保留原失败、已完成角色和同一账本。正式改进需求由用户评估和实施，CodeX只在开发中按授权参与。
- 最新代码验证：01f9b02，440项测试通过（96.08秒）。wheel/sdist构建成功，wheel独立安装后从仓库外验证CLI注册、源码功能和提示词资源；未做额外哈希校验。

最新真实同卡链、费用和研究结论见[当前状态](MASTER_STATUS.md)、[真实续跑](RUNTIME_VERSION_LIVE_RESULT.md)、[费用报告](COST_REPORT.md)。[早期验收记录](E2E_REPORT.md)保留原失败和历史快照，不代表当前执行状态。

L4三组旧对照尚无完整匿名评价，保持未完成，不能据此声称ARC优于直接Pro。任务书允许在预算及材料受限时交付实际完成范围；不通过重复抽卡改写旧失败。[L4原记录](L4_REPORT.md)。

## 文档与保留边界

[逐条实现审计](IMPLEMENTATION_AUDIT.md)及[执行清单](IMPLEMENTATION_CHECKLIST.md)保留早期映射；后续修复以当前状态和细粒度Git提交为准。[参考项目比较](reference-review-notes.md)、[运行用法](../README.md)、[协议纠正](PROTOCOL_CORRECTION.md)。

原始研究数据库、文献、模型响应与工具结果保留在 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation`，不作为测试垃圾删除或推送。旧分支已移除；该历史目录为detached研究档案。当前交付不依赖旧分支bundle或旧MANIFEST。

旧计划和过期生成报告的版本跟踪已清理。三处Windows临时副本的永久删除曾被自动审批拒绝，仍未删除，具体路径见[当前状态](MASTER_STATUS.md)；未绕过拒绝或宣称清理完成。没有执行训练、实验或论文生成。
