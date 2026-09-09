# 当前功能与软件交付

> 2026-09-09 Discover First 改造：当前产品主线、轻量idea交接与本轮验证状态以 [DISCOVER_FIRST.md](DISCOVER_FIRST.md) 为准。下面保留上一轮的交付、测试与费用原记录，不代表新版本已经完成真实验收。

**55a134c：707 passed，0 failed/error/skipped**，2026-09-08 21:08:02 UTC完成全套、sdist→wheel、仓库外隔离安装、38提示词/18任务/3配置、4CLI及依赖检查。唯一两包和SOFTWARE_VALIDATION.json已于21:08:53 UTC同步Windows，原件`work/software-validation-20260908T210458748151Z/`，回执`work/FINAL_PACKAGE_DELIVERY_RECEIPT.json`。

05cf26e上一完整快照为706 passed/1 failed，旧测试精确错误字符串落后于结构化诊断；55a134c改为检查type/loc/supplied，未删除测试，9相关与707全套通过。更早31fc58c/694（当时删除过期逐字trace文案断言）及195失败也是独立历史事件，不能混为本次少测；所有原失败保留。`empty-actual-searches-check.json`仅证明0付费离线恢复。

## 已交付结果与边界

已完成八个已知语义对照、新主题discover→辅助develop→run、两个最终定向纠正和A–E两轮双序比较。原五张无辅助候选均未通过独立科学验收，三张推荐为误放；后续已知2＋4目标辅助修复通过，不能倒算为自主检出或整卡穷尽正确。两轮D/E有局部真实改善，但最终E仍有硬错误，r2自身recheck为revise、新finding未修。计划内运行完成，**自主科学质量验收未通过，不宣称ARC优于直接Pro**。

先读[功能验收](FUNCTIONAL_VALIDATION_RESULTS.md)、[两轮消融](FUNCTIONAL_ABLATION_RESULTS.md)、[旧卡变化](OLD_CARD_CORRECTION.md)，再看模型原报告及独立审计。完整阶段/两轮报告、前后字段、方法成本、双序映射均已复制Windows。最终功能新增上界95.066385 CNY，包含两轮及恢复；父历史累计和授权账本余额见[COST_REPORT](COST_REPORT.md)，不是在线钱包查询。

r1零成本凭据启动错误、r2 B前置矛盾暂停和显式retry均保留，费用未重置。软件接线通过不能替代科学判断。最后169项清理和旧工作树解除登记已完成，原数据与最终包保留，详见[最终收尾](FINAL_CLOSEOUT.md)；五个Windows历史阻断路径不重试删除；源码、付费原件与验证日志保留。以下内容仅为重构前原记录，不是当前包或效果证明。

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
