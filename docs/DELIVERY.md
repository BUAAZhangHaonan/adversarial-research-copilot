> 历史记录：本文描述功能重构前的交付状态。当前实现与验证以 [FUNCTIONAL_REDESIGN](FUNCTIONAL_REDESIGN.md) 为准；旧三组对照不是新流程的有效性证明。

# ARC 当前交付说明

ARC聚焦研究idea抽卡、方案展开与可行性压力测试；实验和论文由人完成。正式源码在g203，唯一master。

同一自然卡 discover → develop → run 三阶段执行完成。

| 阶段 | 状态 | 卡版本 | 判断 | 结束原因 |
|---|---|---:|---|---|
| discover | COMPLETED | 1 | — | no_distinct_direction |
| develop | COMPLETED | 5 | PROMISING | experiment_required |
| run | COMPLETED | 7 | PROMISING | experiment_required |

源码验证 06de446：全套 480 项测试通过（103.44秒）；wheel/sdist构建、仓库外独立安装、CLI与提示词资源核验通过。日志及核验记录为 work/tests-final-reference-diagnostics.log、work/package-build-final.log、work/package-install.log、work/release-verification-current.json。

逐条任务书的实体/证据/版本、提示词资产、SQLite与档案、预算/模型/MCP、三个工作流、中文报告和CLI实现映射见[逐条审计](IMPLEMENTATION_AUDIT.md)。后续协议修复见[当前状态](MASTER_STATUS.md)、[协议纠正](PROTOCOL_CORRECTION.md)，均保留细粒度Git历史。

仅使用DeepSeek V4 Flash/Pro，语义调用max、完整输出上限384000。read_record支持64000字符；工具参数与JSON各一次纠错。改动后的claim移除旧版本引用后重新补证；正式能力需求由用户评估实施。

三组固定材料对照完成 3/3，结果及科学边界见[L4报告](L4_REPORT.md)。本次匿名自动偏好：rendering → direct-Pro；segmentation → ARC；conflict_holdout → direct-Pro。仅有三个固定案例，尚不能证明ARC普遍优于直接Pro。 父账本累计结算 84.810721–84.960337 元；新增228元授权后追加花费上界 27.397953 元，剩余 200.602047 元，预留0、未知调用0。历史花费未重置。

PROMISING是调查价值判断，流程执行完成不等于实验有效、新颖性已证明或论文可发表。非arXiv原文获取作为[可选支线](CAPABILITY_FOLLOWUPS.md)保留，缺失正文不冒充已验证证据。

旧计划和旧报告跟踪已清理；g203研究数据库、文献、模型响应及参考项目保留。三处Windows临时副本删除被自动审批拒绝，未删除，具体路径见[当前状态](MASTER_STATUS.md)。没有执行训练、实验或论文生成，也未做额外哈希校验。
