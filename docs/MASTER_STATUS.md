# ARC master 当前状态

2026-09-07。正式源码为 g203 `/home/g203/zhanghaonan/adversarial-research-copilot`，仅维护master；所有修复保留细粒度提交，不新建分支、不压缩历史。

## 工程完成情况

01f9b02：全套440项测试通过，96.08秒。wheel/sdist构建成功；wheel独立安装后从仓库外验证CLI、模块、64000字符上限、独立纠错额度和提示词资产。日志为 `work/tests-closeout-final.log`、`work/package-build-final.log`、`work/package-install.log`。没有额外文件哈希校验。

- 34cc012：正式需求由用户评估实施，CodeX只在显式开发评估中参与。
- 2e152b4：read_record上限64000字符，分页、预算及恢复验证。
- abc8ee2：工具参数与最终JSON各一次纠错。
- 4563a55 / bd3db80：机械补齐遗漏版本，移除旧版本引用后由Agent重新补证。
- bbdfcad：完整JSON对象前缀的结构错误一次性诊断，原文不裁剪、不改写。
- 8688741：用户显式创建失败任务的新版本，成功角色及预算复用。
- 2cc0384 / b09c859：允许同轮新争点的合法补证请求，并将最终问题/目标/判断分支传递到调查。
- 01f9b02：对未应用的锚点变更修订提供显式纠正入口；原锚点、原卡、旧响应和拒绝诊断保留。

## 真实验收

自然卡为 `card_52bce58017164c2b9594c418eb0cac7b`。原 discover 已完成并保留 MAIN_REPORT v1；CodeX已按授权选卡，未卡在人工选卡审核。

当前 `natural_runtime_versions_v2.develop` 已保存v3，原问题锚点与v2完全一致。protocol_retry2已接受，随后证据重核也已接受：8条支持findings、1条contrary finding均明确绑定claim v3；14次成功工具调用，工具参数纠错0次、JSON纠错1次。页面级核验与ZIP内容级待核仍区分保留。

当前停在 `round1.moderator.evidence_reassessment` 的预算准入（PENDING），**不是新的协议失败**。develop上限25元，已结算上界10.578927元，剩余14.421073元，小于下一次Pro完整输出预留15.912元。run尚未创建，因此同卡三阶段链仍未全部通过。精确状态见 [CURRENT_VALIDATION_SNAPSHOT.json](CURRENT_VALIDATION_SNAPSHOT.json)。

已向用户提出并等待选择：本轮develop/run各临时上限50元，共享原100元父账本（推荐），或保持25元逐次审批，或以当前预算停点结束真实验证。未把默认推荐当成授权，也未追加第二笔develop预算。获准后可从现检查点继续，无须重跑已完成角色。

最初失败是JSON尾随字符、claims字段错层及漏字段；随后定位到同轮新争点被错误拒绝、补证请求未向下游传递，以及新增方法细节写入冻结锚点。均已有对应修复或用户明确的纠正任务，不把它们称为科学否决。具体响应指针和真实补证效果见 [RUNTIME_VERSION_LIVE_RESULT.md](RUNTIME_VERSION_LIVE_RESULT.md)。

父账户始终为 `arc-vnext-validation-20260907`，总上限100元，历史花费不重置。当前已结算快照为57.412830–57.562384元，预留0、未知调用0、父级剩余42.437616元；分项见 [COST_REPORT.md](COST_REPORT.md)。develop已按授权从20追加至25元；run的20→25条件授权尚未使用。正式默认仍每阶段20元。

L4三组旧对照尚无完整匿名评价，保持未完成，不声称ARC优于直接Pro。实验、训练、论文写作及材料访问限制仍由人处理。详细边界见 [DELIVERY.md](DELIVERY.md) 与 [L4_REPORT.md](L4_REPORT.md)。

## 清理与提交边界

已清理本轮g203 `.pytest_cache` 与 `work/package-install-check` 安装测试环境，保留440项测试日志、安装核验记录和wheel/sdist。

已将9份针对废弃pipeline/chat-mode/YAML控制的旧计划从当前树删除；81个旧生成报告停止版本跟踪，但服务器原件保留，历史提交也可追溯。参考项目、输入文档、密钥及真实验证数据库/文献不属于本地测试垃圾，不删除或发布。

上一轮本地清理盘点为下列三处，当时共15150个文件、456905914字节；本轮继续使用已保留的源码镜像，数量未重新盘点。永久删除被执行环境的自动审批以`blocked by policy`拒绝；没有换工具绕过。因此这些本地产物仍未删除，清理不应记成完成：

- `E:\OneDrive\文档\Playground\work\arc-vnext`：临时源码镜像、两个测试环境、缓存和fixture，正式修改已在g203 master。
- `E:\OneDrive\文档\Playground\work\arc-vnext-source.tar`：旧源码传输包。
- `C:\Users\zhn19\Documents\Codex\2026-09-06\new-chat\outputs\delivery-6a350bc`：旧分支交付副本；当前状态以本文件及远程master为准。

本次没有进行文件哈希或SHA256校验；仅使用Git状态/提交关系、文本差异和文件存在性等必要检查。既有运行时用于检查点身份和证据定位的内部机制未因本次运维请求而重构。
