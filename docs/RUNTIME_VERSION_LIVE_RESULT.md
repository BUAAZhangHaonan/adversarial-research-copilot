# 同卡版本恢复与任务重试的真实验证

最终阶段状态与费用见 [MASTER_STATUS.md](MASTER_STATUS.md) 和 [COST_REPORT.md](COST_REPORT.md)。原件位于 g203 私有研究档案 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation`，收尾证据导出为正式源码目录下 `work/runtime-closeout-evidence.json`。

## 已核实的过程

自然 discover `arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover` 保留 MAIN_REPORT 卡 `card_52bce58017164c2b9594c418eb0cac7b` v1。CodeX 依据用户授权选择该卡进入开发验证，理由是问题可以证伪、干预范围可控；新颖性和可行性仍须受到后续质疑，并非代替人类认可成果。

本轮 `natural_runtime_versions_v2.develop` 完成 fresh_verification 和 development，保存同卡 v2。模型本次自行正确填写新版本；“遗漏递增可自动修复”的证据来自旧真实输出的只读回放和工程测试，不冒充本轮在线触发。

运行时从 `claim_d1c_measurement_ambiguity` 新版移除了两条旧版引用：`ev_8ce0b7d7ef922167309283f7949f6261` 和 `ev_29e550f1fa7b0eeb2aca76389d5938f8`。随后 `development.evidence_recheck` 被接受，登记4条findings和4条contrary_findings、共8条面向claim v2的新证据。旧证据、原始输出与原卡不变。

补证任务执行15次成功工具调用，其中 read_record 明确请求并返回30000字符，超过旧24000上限。另一请求在offset=30000返回0，Agent保留只缓存了前缀的限制，没有宣称读完64012字符全文。资产/ZIP/全文可用性仍是适用条件限制；补证用于重新审视可测量性、归因及数据覆盖，不能当作新主张已获实验支持。64000边界、Unicode分页、预算暂停和恢复不重放另由实际Runtime离线测试覆盖。

## Moderator 失败原因与修复

原 round1.proposer 和 round1.skeptic 已接受。原 round1.moderator 的首次最终响应 `call_be9690f1916e482780858df0a3555bd5` 在第1行64058列出现尾随字符。一次修复响应 `call_2f687f58170544cf9dbc4512c6600575` 可以解析为JSON，但四处结构不合约：

- 多余字段 result.claims。
- 缺少 result.proposed_card_revision.claims。
- 缺少 result.external_test_requirements。
- 缺少 result.direction_change。

第一次语法错误遮住了字段错层等诊断，是工程上可修复的问题，不是主张版本未递增或等待人工选卡，也不是科学否决。bbdfcad 补充完整对象前缀的结构诊断，仅作反馈、不接受非法原文；8688741 增加用户显式的新任务版本入口。

用户明确批准后，正式CLI为同一run创建 `round1.moderator.protocol_retry1`。原失败仍为PAUSED_PROTOCOL，原角色结果、卡v2、账本和已发生费用保留。新任务自己的工具参数/JSON各一次纠错机会，没有清零原任务。原版本的成功工具结果随审计输入复用；Agent仍可为科研判断进行新的合法检索。

第一次私有启动脚本误用未提供的 `python -m arc`，在模型调用前失败；改用项目正式 `arc` CLI 后发起任务。该启动错误没有新增付费请求，也没有修改科研输出。

## 工程证据与限制

8688741：428项测试通过，93.35秒；包含严格JSON诊断、失败记录与冻结输入保留、同账本、显式任务版本、已完成角色复用、再次失败须重新明确触发等测试。wheel/sdist构建成功，独立安装后从 `/tmp` 验证CLI、模块与提示词资产。没有额外文件哈希校验。

L4旧三组质量对照仍未完成匿名评价；本轮单卡真实链即使完成，也不能证明ARC优于direct-Pro，更不能证明科研idea成立。实验执行和论文写作始终由人处理。
