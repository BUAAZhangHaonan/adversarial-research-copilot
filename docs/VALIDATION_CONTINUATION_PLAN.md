# 追加授权后的验证顺序

2026-09-07记录；付费调用仍顺序执行，唯一父账户为`arc-vnext-validation-20260907`，上限100元。

1. 让已启动的L4 driver完成既定顺序和固定留出主题，不调整留出提示词。
2. 复用已保存任务，依次恢复本次获批的渲染discover、旧explicit_input.develop、分割对照direct-Pro；三个账户各由20增至25元，授权原件见[BUDGET_EXTENSION_AUTHORIZATION](BUDGET_EXTENSION_AUTHORIZATION.md)。不再追加其他账户。
3. 如自然链没有覆盖当前版本的develop/run入口，而旧检查点因已修复的schema依赖变化不能恢复，则对尚缺入口使用**完全相同的已保存explicit_input**建立显式新run验证当前版本。新run标记`explicit_L2_development_input_not_natural_discovery`，记录原run及输入SHA256；每个完整入口仍默认20元，所有旧费用仍计入同一100元父账户。不是重新抽取或挑选喜欢的科学结论，不是自然同卡L3通过。

第3步只针对当前实现尚缺的入口验收；不复用旧空claims卡、旧developer/proposer/skeptic判断，也不修改旧任务hash。若发生新的协议失败或预算暂停，保留真实停点；本计划不授权自动格式修复次数之外的重试或新的额度追加。不会为了花完父级余额重复同一个已失败案例。

## 已查明的旧依赖变化

旧`explicit_input.run.import`与`explicit_input.develop.round1.moderator`的冻结schema中，`CardDraft.required`没有`claims`；当前schema要求该字段。保存的schema与冻结payload/subject能精确重现旧input hash，换当前schema后的唯一schema差异就是新增该必填字段：

| 任务 | 冻结input hash | 当前schema、同输入重新计算 |
|---|---|---|
| run.import | `a3ce25a854371b3edcbe292ad8773d64783c76e51e7917620b9b23918bc2116f` | `c42bd78a93d47be9e3847ab7f6cdfb5569ce16632e6891361d680ac5e025019a` |
| develop.round1.moderator | `68077b6054a59860e2aef6e95bafb0f00f31d5885c82fbbf02b58cbf8655b6f8` | `45950f5cc31a54a5664082e64f3942ac9b2d2525be0654fc1fc821a289b440c1` |

依赖检查应在新付费请求前返回`TASK_DEPENDENCY_CHANGED_FORK_REQUIRED`。这是只读重算结论，实际恢复结果另记。两个run自身提示词快照完整并与run记录一致；环境快照和当前依赖逐项一致。当前安装的read_record提示词虽已改变，bootstrap恢复时使用run自身冻结资源，因此不把此处错误误记成提示词文件丢失或环境变化。相关runtime/schemas/bootstrap源码与已测bac3659一致。

本文件记录执行计划和依赖审计，不能代替最终`VALIDATION_SNAPSHOT.json`、真实trace或完成判定。
