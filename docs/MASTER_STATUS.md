# ARC master 当前状态

2026-09-08，快照 2026-09-07T18:57:22.498690+00:00。正式源码位于 g203 `/home/g203/zhanghaonan/adversarial-research-copilot`，只维护master，改动按问题细分提交并推送。

同一自然卡 discover → develop → run 三阶段执行完成。

| 阶段 | 状态 | 卡版本 | 判断 | 结束原因 |
|---|---|---:|---|---|
| discover | COMPLETED | 1 | — | no_distinct_direction |
| develop | COMPLETED | 5 | PROMISING | experiment_required |
| run | COMPLETED | 7 | PROMISING | experiment_required |

`COMPLETED`表示有界研究流程执行到结束；`PROMISING`和实验交接不表示idea已经实验验证。全文未核验、资产内容级核验和真正的实验结果须保留在卡片限制及后续研究工作中。

## 实现与工程验证

源码验证 06de446：全套 480 项测试通过（103.44秒）；wheel/sdist构建、仓库外独立安装、CLI与提示词资源核验通过。日志及核验记录为 work/tests-final-reference-diagnostics.log、work/package-build-final.log、work/package-install.log、work/release-verification-current.json。

- 34cc012：正式需求由用户评估实施，CodeX仅参与显式开发评估。
- 2e152b4 / abc8ee2：read_record上限64000字符，分页与恢复；工具参数和JSON各一次纠错。
- 4563a55 / bd3db80：机械补齐遗漏的主张版本，移除旧版本引用，再由Agent重新选择或补充证据。
- bbdfcad / 8688741：一次性结构诊断、保留原失败的显式任务新版本。
- 2cc0384 / b09c859：同轮新争点的合法请求及最终补证请求向下游传递。
- 01f9b02：冻结锚点误写的显式纠正入口，保留原锚点与原响应。
- 0fb45fd / 344ef67 / e5b85bb：COMPOSE同响应新主张的请求、已授权父预算复用、固定材料对照的显式纠正版本。
- 1aa8107：真实读取确认只有元数据后，允许Agent撤回错误引文并保持未决；仍保留verified引文、未读取或未披露限制的输出拒绝。
- 6b19f4e / 5c395dc：定位争点关闭依据的具体版本错误；卡已保存后的显式应用纠正，仅修争点依据与状态，保留卡片并支持再次显式纠正。
- c410055：报告区分当前未完成任务与历史失败；已完成阶段保留原错误及追踪入口，不再误报当前阻塞。
- 06de446：固定材料纠正反馈指出无效引用的完整字段路径、原值和合法引用目录，不猜测证据替换。

原失败包括JSON尾随字符/字段错层、合法新争点请求被拒、方法细节写入冻结锚点，以及元数据来源撤回被错误拦截；随后争点关闭仍引用旧版证据的失败，通过明确诊断和应用纠正任务处理。均保留对应修复和原始记录。不是未递增版本且不给修改机会，也不是等待用户选卡。CodeX已按开发授权选定自然卡，并保持原研究问题。

## 对照与费用

三组固定材料对照完成 3/3；逐组科学缺陷、正式selection和匿名自动评价见[L4报告](L4_REPORT.md)。本次匿名自动偏好：rendering → direct-Pro；segmentation → ARC；conflict_holdout → direct-Pro。仅有三个固定案例，尚不能证明ARC普遍优于直接Pro。

父账本累计结算 84.810721–84.960337 元；新增228元授权后追加花费上界 27.397953 元，剩余 200.602047 元，预留0、未知调用0。历史花费未重置。 用户所述“当天61元”为账户/日期口径，不能直接等同项目累计账本。完整分项见[费用报告](COST_REPORT.md)。生产默认仍每阶段20元；本次开发共享原已花57.562384元加新增228元的累计限额285.562384元。

非arXiv全文获取需求及候选方案见[能力支线](CAPABILITY_FOLLOWUPS.md)。正式版本由用户评估实施；CodeX不在生产环路。

## 清理与原件

已清理废弃计划、旧生成报告的版本跟踪和本轮g203测试缓存/安装临时环境，保留必要测试日志与安装包。参考项目、输入材料、密钥及真实数据库/响应不属于测试垃圾，不删除或推送。

以下三处Windows临时副本永久删除曾被自动审批以 blocked by policy 拒绝，未绕过，仍未删除：

- `E:\OneDrive\文档\Playground\work\arc-vnext`
- `E:\OneDrive\文档\Playground\work\arc-vnext-source.tar`
- `C:\Users\zhn19\Documents\Codex\2026-09-06\new-chat\outputs\delivery-6a350bc`

本次没有额外文件哈希或SHA256校验。既有运行时检查点身份与来源定位机制保留。

研究原件保留于 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation`。逐条实现映射见[IMPLEMENTATION_AUDIT](IMPLEMENTATION_AUDIT.md)，真实任务指针见[当前快照](CURRENT_VALIDATION_SNAPSHOT.json)。
