# ARC master 当前实施与验证状态

2026-09-07。g203 正式源码为 `/home/g203/zhanghaonan/adversarial-research-copilot`，只维护 master。原有细粒度提交保持完整；没有新建分支、压缩、重写或合并提交。旧 detached 工作目录保留真实研究档案。

## 已实现

- 34cc012：正式改进需求默认由用户评估、实施。CodeX 仅能显式参与开发评估，正式服务不依赖 CodeX。
- 2e152b4：read_record 单次上限启用 64000 字符；分页、预算暂停及恢复不重放通过实际 Runtime 离线回归。
- abc8ee2：每个 Agent 任务工具参数和最终 JSON 各一次纠错机会，分别持久化计数。这不限制 CodeX 开发修复。
- 4563a55：内容、条件或类型改变却遗漏 claim 递增时，runtime 机械派生版本并保存来源审计。
- bd3db80：移除新版主张中的同目标旧版本证据引用，重新调查并重评受影响裁决；原始输出、旧卡、旧证据不变。正常的有界补证仍可继续。

详细行为见 [PROTOCOL_CORRECTION.md](PROTOCOL_CORRECTION.md)。[版本修复记录](CLAIM_VERSION_SIDE_TASK.md)和[读取上限记录](READ_LIMIT_SIDE_TASK.md)保留历史评估，并已注明当前用户决定；它们不是仍待启动的支线。

## 当前验证

源码 bd3db80 的 g203 全套离线测试 **402 passed in 88.87s**。日志：`work/tests-evidence-reselection-final.log`。sdist/wheel 构建及仓库外独立安装通过，确认 64000 schema、独立纠错计数、正式用户评估及补证角色资产可用。

上一轮自然卡真实输出的只读回放已经通过完整修订校验：补齐一个 conditions 改变后遗漏的版本增量，移除两条 v2 claim 对各自 v1 证据的引用。旧失败响应、原卡 v1、PAUSED_PROTOCOL 状态不变。这项回放验证的是修订协议，不是新一轮真实科研判断。

同卡真实验证已于 2026-09-07 13:40:28 UTC 启动：`arc-vnext-validation-20260907.natural_runtime_versions_v2.develop`，源码 bd3db80。develop 完成后选择其卡版本进入同前缀的 run；当前还未收到最终结果，不能宣称三阶段通过。日志：`work/live-runtime-version-validation.log`；最终结果：`work/runtime-version-validation-result.json`。

## 已定位的直接原因

此前停点不是无解：developer 提示词笼统称 runtime 创建版本，代码却要求模型给每条改变的 claim 递增。真实输出中两条已写 v2，另一条只改变 conditions 却仍写 v1。版本修复后又暴露了两条旧版本证据引用不匹配。以上已经实现修复，并没有通过追加模型修复次数或改写旧响应冒充成功。

64000 未启用是此前被我留作可选支线，不是确认存在技术障碍；用户选择后已经完成工程验证并启用。

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

本轮新验证沿用原100元父账本，不重置已发生费用。启动前总计46.833939–46.983457元、剩余53.016543元、预留0、未知调用0；develop/run 新账户各20元。所有后续请求仍串行、完整输出预算准入，不切换模型或缩减输出上限。

原自然 discover 已给出一张 MAIN_REPORT 卡，CodeX 已在开发验证中记录选卡理由并让它进入后续阶段。不存在需要等待人工审核才能继续的停点。科学结论仍可能降级为 NEEDS_EVIDENCE 或需要实验；这与工程协议暂停分别报告。

L4 旧三组对照尚无完整匿名评价，不能以本轮工程测试或单卡贯穿宣称质量对照通过，更不能据此声称 ARC 优于 direct-Pro。原记录见 [L4_REPORT.md](L4_REPORT.md)。

## 清理与提交边界

已将9份针对废弃pipeline/chat-mode/YAML控制的旧计划从当前树删除；81个旧生成报告停止版本跟踪，但服务器原件保留，历史提交也可追溯。参考项目、输入文档、密钥及真实验证数据库/文献不属于本地测试垃圾，不删除或发布。

上一轮本地清理盘点为下列三处，当时共15150个文件、456905914字节；本轮继续使用已保留的源码镜像，数量未重新盘点。永久删除被执行环境的自动审批以`blocked by policy`拒绝；没有换工具绕过。因此这些本地产物仍未删除，清理不应记成完成：

- `E:\OneDrive\文档\Playground\work\arc-vnext`：临时源码镜像、两个测试环境、缓存和fixture，正式修改已在g203 master。
- `E:\OneDrive\文档\Playground\work\arc-vnext-source.tar`：旧源码传输包。
- `C:\Users\zhn19\Documents\Codex\2026-09-06\new-chat\outputs\delivery-6a350bc`：旧分支交付副本；当前状态以本文件及远程master为准。

本次没有进行文件哈希或SHA256校验；仅使用Git状态/提交关系、文本差异和文件存在性等必要检查。既有运行时用于检查点身份和证据定位的内部机制未因本次运维请求而重构。
