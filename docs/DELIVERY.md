# 当前软件交付快照

**31fc58c：694 passed，0 failed/error/skipped**，已于2026-09-08 17:58:20 UTC完成全套测试、sdist→wheel构建、仓库外隔离安装、38份提示词/18个注册任务/3份配置资源、4个CLI帮助及依赖检查。Windows唯一wheel/sdist与同组 `SOFTWARE_VALIDATION.json` 已更新；服务器原件为 `work/software-validation-20260908T175518443480Z/`。

**695→694的原因是删除过期文案断言，不是跳过检查。** 195240b把机械搜索记录重建交回runtime后，旧 `test_investigator_searches_copy_actual_trace_identity_and_coverage` 仍要求提示词逐字出现“让模型复制全部搜索trace”的三句旧指导，因此上一快照实际为694 passed / 1 failed，记录保留在 `work/software-validation-20260908T175026940841Z/`。31fc58c只删除该过期文案测试；当前694项重新完整运行，没有skip。搜索来源与科学引用行为的运行时检查仍在。

`work/empty-actual-searches-check.json` 另记录零付费离线恢复验证：模型不回显actual_searches时，从实际工具trace重建一条搜索；正常路径和规范化前中断恢复两例都通过，各两次mock模型请求、0次JSON纠正、paid_calls=0。它验证软件恢复，不是新付费科研效果；该JSON已同步Windows交付目录。

软件验收不等于科学验收。当前各真实阶段结果见本轮独立阶段报告及[功能验收结果](FUNCTIONAL_VALIDATION_RESULTS.md)；下方原06de446交付、费用和三组对照仅作历史，不是当前包或本轮效果证明。

## 当前功能交付与仍待完成

已完成八个已知语义对照，以及新主题discover→开发辅助develop→run全流程。无辅助discover五张候选均未通过独立科学验收，其中三张被ARC误推荐；develop/run真实改善但仍漏检。之后另建的自然final-correction两项、旧卡final-correction四项已知目标均已实改保存并通过定向核对，不能倒算为自主检出、整卡穷尽正确或未见科研质量提高。

完整阶段报告、实际前后字段、独立审计和费用已复制Windows交付目录。建议先读[本轮验收结果](FUNCTIONAL_VALIDATION_RESULTS.md)与[旧卡各轮变化](OLD_CARD_CORRECTION.md)，再对照各运行报告中的ARC推荐。当前已完成子账户费用上界83.246771 CNY，包含r1的10.081649、不包含在途r2，也不是父账本历史总额。

[A–E r1](FUNCTIONAL_ABLATION_RESULTS.md)已完成全条件和双序评价，r2在途。新审推动局部实改但E仍有硬错误；跨轮独立核对和人工研究价值判断待完成。首启动漏传`--env-file`产生的0调用/0费用凭据错误已独立保留，随后同ID恢复，不能把它当模型效果。当前没有完成的ARC优于Pro结论。源码、运行原件与当前软件包按[状态入口](MASTER_STATUS.md)分别定位。

## 功能重构前的交付原记录

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
