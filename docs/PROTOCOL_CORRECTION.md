# 工具协议纠正与改进需求

2026-09-07。当前规则依据用户后续选择更新，早期的共享纠错额度及默认 CodeX 评估已被替换。

## 每个 Agent 任务分别计数

工具参数错误有一次纠正机会，最终 JSON 结构错误也有一次。两个类别互不消耗对方额度；这是正式运行时一次 Agent 任务的限制，不限制开发期间 CodeX 修代码、运行测试及开启明确的新版本验证。

原生工具的参数不符合公开 schema 时，运行时保存原始调用、报错字段、校验器和实际 schema，返回 rejected_before_execution，不执行非法调用，也不将其计为取证成功。该反馈没有工具付费预留。

模型可以纠正被拒绝的调用，或返回 blocked envelope 与具体改进需求。纠正保持原工具、调用顺序、目标及所有合法字段；只允许报错的完整字段路径变化、缺失的必填字段补回。不可解析参数没有可靠原目标，只能提出 blocked 需求。工具纠正成功后继续正常研究调用；再次同类非法或改目标则暂停。最终 JSON 修复禁用工具，不重新启动研究取证。

repair_counts 分别记录 tool_arguments 和 output_json，repair_count 保留合计。恢复会保留各类已用次数；成功的兄弟调用不会重放。原始响应、错误反馈和修复响应全部保留。

## 主张版本和证据

主张的 text、conditions 或 kind 改变而版本仍与原版相同，运行时机械派生下一版本，并同步同目标的版本元数据。不会改写科研正文、既有争点目标或原始模型响应。模型提出的合法新版本保持原样；倒退版本、无法确定新争点所属版本等仍严格拒绝。

用户已选择：新版主张移除同一主张旧版本的证据引用，交由 Agent 重新选择或补充证据。旧证据记录和原卡保持完整，旧结论不能自动转移到新主张。移除引用后的补证、重新判断及恢复检查以当前收尾报告为准。

## 64000 字符读取

read_record 的单次公开上限已从 24000 提高到 64000 字符，默认仍为 12000。64000 指字符，不是 token。原文、offset、version 和来源元数据保持原语义，64001 在执行前拒绝。

实际 build_tools 与 Runtime 测试覆盖 Unicode 分页、越界纠正、预算暂停、增加测试额度后重建 Runtime 恢复及成功调用不重放。模型 max_tokens 和请求预算规则没有改变。扩大上限不代表已证明费用或质量改善。

## 改进需求的评估责任

有工具的角色可以 request_capability 后继续研究；所有任务均可在最终 envelope 的 capability_requests 登记提议。正式需求进入 pending_user_review，由用户评估和实施。Agent 不会自动改工具上限、安装服务、增加预算或启动新任务。

只有开发阶段显式指定 --reviewer codex --development-review 才记录 CodeX 评估；正式服务不调用 CodeX。需求原文、评估者及 production/development 上下文保留。历史记录不伪造评估者，也不改写成新的授权。用法见 [CAPABILITY_REQUESTS.md](CAPABILITY_REQUESTS.md)。

## 验证边界

离线回归涵盖两类额度各一次、同类耗尽、目标保护、预算与中断恢复、原始记录不可变及生产/开发责任隔离。真实模型调用与离线协议模拟分别报告。当前源码、最终测试和真实同卡三阶段结果见 [MASTER_STATUS.md](MASTER_STATUS.md)；旧失败仍保留为历史证据。

## 显式创建失败任务的新版本

原任务的一次 JSON 纠错耗尽后，原失败记录保持 PAUSED_PROTOCOL。用户检查原因后可执行：

```bash
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data retry-task RUN_ID --task-key round1.moderator --reason "已审阅结构错误，授权新任务版本"
```

新任务标识追加 `.protocol_retry1`，后续版本依次递增。它沿用当前卡、原冻结研究输入及同一预算账户，并接收原失败响应、具体错误和成功工具结果。完成角色直接复用；原失败不覆盖、费用不重置。新任务各有一次工具参数纠正和一次 JSON 纠正；进一步失败仍须用户显式决定，系统不自动循环创建版本。正式服务没有 CodeX 环节。本次开发验证由 CodeX 按用户明确选择调用这个相同 CLI 入口。

JSON 出现完整对象后多余字符时，第一次反馈同时包含语法错误与完整对象内的字段错误。这些附加诊断仅用于反馈，不接受、裁剪或修改原始输出。第二次结构失败持久保存具体路径，便于用户判断是否创建新任务版本。


若 moderator 的 JSON 已接受但拟议卡片因 `problem_anchor_changed` 被拒绝应用，用户也可显式 retry-task：入口重新验证原锚点差异、当前卡与缓存/原响应一致，保存拒绝诊断和旧缓存，只撤销该逻辑任务的待应用结果缓存。原 TaskRecord 与原文保留，原卡不变；新任务收到精确原锚点，要求把实现细节放回对应字段。该例外不开放其他已接受任务的任意重跑，也不自动批准方向变更。


## 固定材料对照的显式纠正

```bash
arc --env-file /path/to/existing/.env --data-dir /path/to/private/arc-data retry-comparison-task SOURCE_RUN --system ARC --task-key compose --reason "修复已审阅的协议失败，保持冻结材料"
```

支持ARC的frame/family/compose/novelty/selection，direct-Pro的compose/novelty/selection，以及evaluator的judge。只为指定技术失败或blocked步骤创建新任务版本，成功步骤与候选不重抽；needs_evidence科学结果不能通过这个入口重抽。冻结材料、原提示词bundle、旧响应和费用保持不变，新任务接收结构化错误与原响应，工具仍禁用。

已存在的验证父账户复用其明确授权，新对照账户使用settings.budget_cny（默认20元），不会将已有账户强行重置为100元或覆盖已批准的阶段额度。

## 原文不可得时的引文撤回

原文复核仍要求对每个失败来源执行真实的 read_record。若返回明确为零缓存、需要重新抓取的元数据记录，Agent 可以撤回该来源的全部原文引述：每条对应 finding 必须为 source_unavailable、unresolved、inference、excerpt=null，并填写访问限制。满足这些条件后继续科学评审，不把“正文不存在”误判为“没有执行读取”。未读取、仍保留验证引文、未明确披露限制的输出继续拒绝；原失败、原始响应和费用记录保留。此处允许记录未知，不意味着补齐证据或自动通过科学结论。

## 卡已保存、争点关闭依据失效时

若卡片已经保存，后续争点应用因 `empirical_resolution_requires_verified_claim_evidence` 拒绝，`retry-task` 支持为当前待应用的 moderator 裁决创建显式纠正版本。入口重新验证原响应与缓存、已保存卡及其创建记录一致，并以不写入状态的方式复现同一错误。诊断指出具体争点、要求的主张版本和每条提交证据的版本、验证状态及关系。

新任务使用已保存的当前卡和当前证据，旧输入与原响应另存审计，沿用原预算。它只纠正争点依据、状态和相应裁决；必须返回 `proposed_card_revision=null`、`direction_change=null`，不能借此改卡、转向或跳过补证。选择不出合格证据时，应保留未决，而不是降低验证门槛。恢复直接进入这一待应用裁决，已完成角色和补证任务不重跑。

新任务仍可各用一次工具参数和JSON纠错。若再次失败，用户可以再次显式创建任务版本，继续使用当前卡与被冻结的纠正范围；系统不会自动循环创建新任务。CodeX在本次开发授权下代为操作，正式服务仍由用户触发。
