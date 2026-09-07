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

## 开发输入暴露的资源协议可见性修复

`explicit_input_schema_v2.run.import`的首稿通过了当时公布的JSON Schema，却违反既有Pydantic规则：0张GPU与正GPU-hours不一致。一次格式修复又产生非法JSON，真实暂停和原件均保留，见[L2协议审计](L2_SCHEMA_FORK_PROTOCOL_REVIEW.md)。这属于开发用例暴露的协议实现缺口，不是留出主题的科学结果调参。

在正在执行的v2 develop结束后，将既有资源单位、GPU配置及0 GPU工时约束同步到公布schema，不改变原校验标准。完整工程测试与独立wheel安装通过后，用原`explicit_input.run`完全相同的输入进行一次`explicit_input_schema_v3.run`实际验证，独立默认20元账户仍归原100元父账户。记录代码提交、输入hash和原run；不复用旧科学判断、不修改原输出。该验证仅用于修复后的run入口，遇到新的暂停保留停点，不增加修复次数或额外预算，也不重跑留出对照。

v2 develop最终停于`AFFECTED_CLAIMS_COVERAGE`：它列出全部四条主张，但只有两条实际变化。原有验证器要求精确差集，提示词却没有说明“不含未变项”，因此在同一批修复中将该既有规则追加至developer Markdown，只适用于已有原卡的修订，不改变IMPORT语义或校验标准。旧稿与失败记录保留，不直接修剪列表后重判成功；后续仍是上段唯一v3 run验证。
