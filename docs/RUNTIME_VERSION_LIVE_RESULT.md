# 同卡版本恢复与任务重试的真实验证

最终阶段状态与费用见 [MASTER_STATUS.md](MASTER_STATUS.md) 和 [COST_REPORT.md](COST_REPORT.md)。原件位于 g203 私有研究档案 `/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation`，收尾证据导出为正式源码目录下 `work/runtime-closeout-evidence.json`。

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


## 后续定位：同轮新争点与锚点条件

protocol_retry1 未消耗工具参数或JSON纠错，响应结构已合法。运行时曾以 `evidence_request_issue_id_not_supplied_to_task` 拒绝其对本轮新建 `issue_sk_cw_1` 的请求。2cc0384 允许完整moderator裁决引用自己声明且指向当前主张的新争点；未知目标与主张不匹配仍拒绝。b09c859 将完整裁决中的问题、文献目标和判断分支传递给实际调查，并只采用最终重评裁决的请求。保存原响应的零新增调用复核通过；该代码快照436项测试通过（95.11秒）。

恢复后，protocol_retry1 的结构化结果被接受，但 proposed_card_revision 的 problem_anchor.conditions 增加了外观距离统计、几何档位预注册和测量路径细节，触发 `problem_anchor_changed`，卡v3尚未保存。这与最初JSON错层和旧版本证据问题不同。用户明确选择保持原锚点，让Agent把这些内容放回方法/测量字段，创建新的显式纠正任务；不由CodeX直接改科研文本，也不把它当作已经批准的研究转向。


## 2026-09-08 续跑终点

同一自然卡 discover → develop → run 三阶段执行完成。

| 阶段 | 状态 | 卡版本 | 判断 | 结束原因 |
|---|---|---:|---|---|
| discover | COMPLETED | 1 | — | no_distinct_direction |
| develop | COMPLETED | 5 | PROMISING | experiment_required |
| run | COMPLETED | 7 | PROMISING | experiment_required |

原锚点纠正后已保存v3，随后8条findings和1条contrary finding绑定claim v3。新增余额授权后Pro重评接受并保存v4，进入定向检索。第一次检索把snippet挂到无正文的源上，原任务保持PAUSED_PROTOCOL。独立source_recheck真实读取确认metadata-only，撤回excerpt并改为source_unavailable/unresolved/inference；1aa8107修复必须非空正文的误拦截，原响应零新增调用复核后复用，继续第二轮。

develop第二轮完成并保存卡v5，以PROMISING/experiment_required结束。run进一步修订为卡v6，测量主张升至v4，移除9条旧版引用后重新补证，8条支持和1条限制证据绑定当前主张；重评保存卡v7。随后一个争点的关闭依据仍选用了主张v2/v3的旧证据，因此应用校验拒绝。6b19f4e/5c395dc补齐精确诊断和已保存卡的显式纠正入口，要求Agent重新选取当前版本证据或保持未决，禁止借纠正任务改卡、转向或降低证据门槛。最新任务结果以本页阶段表和当前快照为准。

源码验证 06de446：全套 480 项测试通过（103.44秒）；wheel/sdist构建、仓库外独立安装、CLI与提示词资源核验通过。日志及核验记录为 work/tests-final-reference-diagnostics.log、work/package-build-final.log、work/package-install.log、work/release-verification-current.json。

父账本累计结算 84.810721–84.960337 元；新增228元授权后追加花费上界 27.397953 元，剩余 200.602047 元，预留0、未知调用0。历史花费未重置。 此次预算已按用户授权自主分配，未重复申请阶段额度。最终原始响应路径、纠错计数与任务状态见[当前快照](CURRENT_VALIDATION_SNAPSHOT.json)，私有详细导出为正式仓库 work/runtime-closeout-evidence.json。旧失败任务仍保留，不代表最终流程仍失败。

三组对照的最新结果以[L4报告](L4_REPORT.md)为准。自然单卡贯穿与固定材料自动评价均不替代专家科学判断、实验和论文工作。
