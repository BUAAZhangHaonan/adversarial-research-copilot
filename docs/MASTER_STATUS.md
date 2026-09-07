# ARC master 收尾与未通过验收说明

记录日期：2026-09-07。当前源码入口为 g203 `/home/g203/zhanghaonan/adversarial-research-copilot` 的 master。原29个开发提交完整保留，采用快进合并，没有squash、rebase或新建分支。任务分支已删除；原验证目录保留detached HEAD，作为已保存运行的档案，不作为开发分支。

## 结论

协议纠正和任务改进提议已经实现并推送至 master；最终370项离线测试通过。工具参数和最终JSON共享一次纠正，保留成功调用、原目标和预算边界；需求经过CodeX评估后可导出用户支线说明。详见[协议纠正](PROTOCOL_CORRECTION.md)及[已评估的64000字符支线](READ_LIMIT_SIDE_TASK.md)。当前读取上限仍为24000字符。

真实总验收仍未通过。旧discover完成一张MAIN_REPORT卡，旧develop/run及三组质量对照未完成。本轮自然同卡新运行版本 `arc-vnext-validation-20260907.natural_tool_correction_v1.develop`（源码21b0cd2）完成JSON纠正，但因一条改写conditions的claim没有递增版本而暂停；原卡仍为v1，run未启动。详见[真实复验结果](PROTOCOL_CORRECTION_LIVE_RESULT.md)。旧失败原件不变，不把工程测试通过等同于端到端通过。

## develop 与 run 的历史停点（纠正路径实施前）

| 运行 | 原因 | 已修或仍缺什么 |
|---|---|---|
| 自然卡develop | read_record请求limit=30000，公开上限为24000；执行前被拒绝。 | 参数校验正确，但运行时直接暂停，没有一次受控参数纠正反馈。 |
| 旧explicit develop | 冻结的CardDraft schema缺少后来新增的必填claims；恢复返回TASK_DEPENDENCY_CHANGED_FORK_REQUIRED。 | 防止旧协议被冒充新成功；追加预算不能解决依赖变化，需要明确的新版本验证。 |
| explicit schema v2 develop | 首稿JSON字段错层；一次修复后，affected_claims列了4条，但真正变化仅2条。 | 精确差集规则此前未充分告知模型，a14da30已补入Markdown。旧任务已经用过一次结构修复，不能随意增加重试或手工删两项后改判成功。 |
| 旧explicit run | metadata-only来源被反复空读。 | 535357d已补充缓存范围与无正文说明；后续验证没有把旧运行改成成功。 |
| explicit schema v2 run | 0张GPU却有正GPU-hours触发隐藏的跨字段校验；一次修复稿又成为非法JSON。 | 97d4766已把可表达的资源规则公开到schema；没有修改旧失败输出。 |
| 最新schema v3 run | read_record请求limit=52265，超过已公开的24000上限；执行前被拒绝。 | 新schema已经实际发送，但工具参数错误仍无纠正路径，故run未完成。 |

原件与更详细的错误定位见仓库中的FINAL_RUN_PROTOCOL_REVIEW、NATURAL_DEVELOP_PROTOCOL_REVIEW、REAL_TARGETED_RETRIEVAL_REVIEW和L2_SCHEMA_FORK_PROTOCOL_REVIEW。保留这些历史审计用于定位问题，不把它们当作当前开发指令。

## 费用与人工审核

本轮复验开始前累计估计45.154048–45.303543元，原100元父预算剩余54.696457元。此前最终停点是协议错误，不是费用不足，因此不抹除旧账或重置100元；本轮新的调用继续计入该父账本。本轮费用1.679891–1.679914元，当前总计46.833939–46.983457元，剩余53.016543元；预留0、未知调用0。

自然卡已经通过selector，并由开发E2E显式选择进入develop。不存在“等人批准discover才继续”的停点，因此由CodeX代替用户再做一次品味审核不能绕过本次错误；已经生成的科学判断也不应被人为改成通过。

## 本轮实现与验证

已完成参数错误分类与完整字段路径反馈；一次有界纠正及恢复；任务改进需求登记、CodeX评估、用户执行交付；同时出现多个错误的一次完整反馈。master分成独立提交记录这些变化，没有新建分支或压缩历史。

主仓库完整离线测试370项通过（79.86秒）；独立wheel安装检查确认新模板随包加载。自然同卡复验已停止；新的claim版本错误已登记CodeX评估，推荐先澄清版本职责，备选为runtime统一分配claim版本，详见[优先支线](CLAIM_VERSION_SIDE_TASK.md)。没有手工修改旧输出或重新给予原任务纠正次数。64000字符的容量试验是已评估的可选支线，尚未执行；建议先修复已定位的版本职责问题，再按测得收益决定是否提高读取上限。

## 清理与提交边界

已将9份针对废弃pipeline/chat-mode/YAML控制的旧计划从当前树删除；81个旧生成报告停止版本跟踪，但服务器原件保留，历史提交也可追溯。参考项目、输入文档、密钥及真实验证数据库/文献不属于本地测试垃圾，不删除或发布。

上一轮本地清理盘点为下列三处，当时共15150个文件、456905914字节；本轮继续使用已保留的源码镜像，数量未重新盘点。永久删除被执行环境的自动审批以`blocked by policy`拒绝；没有换工具绕过。因此这些本地产物仍未删除，清理不应记成完成：

- `E:\OneDrive\文档\Playground\work\arc-vnext`：临时源码镜像、两个测试环境、缓存和fixture，正式修改已在g203 master。
- `E:\OneDrive\文档\Playground\work\arc-vnext-source.tar`：旧源码传输包。
- `C:\Users\zhn19\Documents\Codex\2026-09-06\new-chat\outputs\delivery-6a350bc`：旧分支交付副本；当前状态以本文件及远程master为准。

本次没有进行文件哈希或SHA256校验；仅使用Git状态/提交关系、文本差异和文件存在性等必要检查。既有运行时用于检查点身份和证据定位的内部机制未因本次运维请求而重构。
