# 已授权 rendering 恢复：真实复用审计

本次核查截止：**2026-09-07 09:17:54.630269 UTC**。SQLite 使用 `mode=ro`，最后一次查询在同一只读事务快照内完成；没有等待当前 Pro、调用模型/MCP、操作进程、修改账本或科研状态。本文仅新增本地审计记录。

## 结论

启动时间 `09:15:36.554661 UTC` 之后，frame、shared investigation、draw1 archive、next、compose、card archive **均没有新增模型或工具账本行**。六个任务仍为此前 ACCEPTED，已保存结果和 run checkpoint 均存在。新调用全部归属于原 `draw1.novelty`，不是重做前序阶段。

原 `card_52bce58017164c2b9594c418eb0cac7b` 仍仅有 v1，正文与已保存 compose 候选完全相等；campaign 仍只开始过 draw1。费用继续使用原 rendering 账户，上限为获批的 **25 CNY**，其父账户仍为原 **100 CNY** 总账。

截止时 run 为 RUNNING、novelty 为 IN_FLIGHT。以上只证明已经观察到的恢复复用和账本归属，**不证明 novelty、selector 或整个阶段完成**。

## 任务与调用复用

Run：`arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover`。

| task 后缀 | 恢复前模型 / 工具账本行 | 恢复后模型 / 工具账本行 | 原 ACCEPTED 更新时间 UTC |
|---|---:|---:|---|
| `.frame` | 4 / 5 | 0 / 0 | 06:54:22.327248 |
| `.shared_investigation` | 11 / 46 | 0 / 0 | 07:47:43.143026 |
| `.draw1.archive` | 4 / 6 | 0 / 0 | 07:49:25.991120 |
| `.draw1.next` | 11 / 10 | 0 / 0 | 07:53:56.059164 |
| `.draw1.compose` | 6 / 10 | 0 / 0 | 08:01:13.247383 |
| `.draw1.card_archive` | 3 / 6 | 0 / 0 | 08:02:16.740476 |
| `.draw1.novelty` | 3 / 15 | 3 / 7 | 当前尚未 ACCEPTED |

依据是原账户全部 `budget_calls` 的 `metadata.task_id` 与开始时间；以实际启动时刻分界，未只靠界面状态或日志文字推断。没有开始时间的行按创建时间检查，避免遗漏预留但尚未发送的调用。

三次新模型调用均属于同一 `draw1.novelty`：

| call_id | 开始 UTC | 截止状态 | 已结算 CNY / 仍预留 CNY |
|---|---|---|---|
| `call_450af53ff9da462d8fb14c65cf4a22ac` | 09:15:38.960752 | SETTLED，09:16:09.091876 | 0.923951–0.923952 / 0 |
| `call_44bd95afee2140308ac2835f50268e2b` | 09:16:42.154144 | SETTLED，09:17:10.741506 | 0.146580–0.146581 / 0 |
| `call_9f30fc1c540c4bad9cf73ece9ab3083d` | 09:17:17.905352 | IN_FLIGHT | 未知 / 15.912000 |

新增的七条工具调用已 SETTLED 为 0 CNY，分别为 `tool_651cbfda30b44f989d5b96b001b90187`、`tool_13a2d57f0e524156ababc2cdefa97904`、`tool_45692761c55743f79beac5a588ac8dc6`、`tool_9f0399ea69d1497e9546a3a76e24dc67`、`tool_75624b657b7e407890e4bd988d458cc5`、`tool_539efc307900492697339ffb0c6a4599`、`tool_da943011108842188339710f24c27d7a`。

恢复后截至快照新增已结算费用为 **1.070531–1.070533 CNY**，另有上述未结算模型调用的预留。未将预留当成实际花费，也未把这笔增量误写为整条 run 的总费用。

## 原卡与抽卡次数

- Card：`card_52bce58017164c2b9594c418eb0cac7b`，SQL 中仅版本 `[1]`，创建于 `08:01:13.357874 UTC`；`draft == run.state['draw1.compose']['card_candidate']` 为 true。
- Card 原始数据库 `data` UTF-8 SHA256：`7383353c4876a14efbab7fd746cec941e340c790a6dedcf361be60c50310f7b1`。
- Campaign：`campaign_f41ce4c25f514bd9b28867854dcad96c`；`draws_started=1`。
- `draws` 表只有 `campaign_f41ce4c25f514bd9b28867854dcad96c.draw1`，ordinal=1，首次开始时间 `07:48:19.149639 UTC`，早于本次恢复。没有第二张抽卡准入记录。
- Run 的 card 指针及 `state.draws` 中 card 指针均仍指向上述 card v1。

## 原状态文件与账户证据

根目录：`/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation/artifacts/`。各任务完整原件路径由 SQLite `tasks.data.response_artifact_path` 给出，位于 `runs/<上述run>/tasks/<任务摘要>/states/`。本次读取的文件及 SHA256：

| task | state 文件 | SHA256 |
|---|---|---|
| frame | `51c3a0be132345828a973e0225e95b50.json` | `c9107aca52b45fc9cbb2b36bca7c3e28197f1d2f874d1dd44f665676d029b69f` |
| shared investigation | `9db960e6487a4593b3cac9d527ba7e20.json` | `795af4d051381645d9117db14128cd9cf25fcf842854b324bf4fc6005de4b7b5` |
| archive | `481552cf326e45d3b093ffd2593cc0c5.json` | `abff3024c6b8b5e748a114c012ec1521e6cbd1aedae37fe1c9d3f8606e6dfd71` |
| next | `e81b5335ec9a4944a2bfac25e9b8e650.json` | `b97825fa9db6612694cf2d2829b71d5231b1c605ef27371ad256d0db4352d836` |
| compose | `ec6ada6228b34f1bb5a9f532a01cb0ed.json` | `30ccf3c668d323bb4df2bd98ef9765b2e32bb1e6c91e802b523f17eb58470ac4` |
| card archive | `26bd65d38bfc4c4b8e83214e128b3182.json` | `3f179dd70af14e5b8ac82b85d1dc29057db9a5936e5cbb026243db05d9e11fb0` |

frame、shared、archive 的这三个哈希也与本次恢复之前的只读观察完全一致；其余三项是本次为后续复核记录的哈希，不伪称此前已独立持有全部基线哈希。

账户原始行：rendering `account_id` 等于上述 run，`parent_id=arc-vnext-validation-20260907`，`limit_micro=25000000`，创建于 `06:53:38.137449 UTC`；父账户 `limit_micro=100000000`、`parent_id=null`，创建于 `02:24:51.259705 UTC`。新调用仍落在该旧子账户，不是另开账户或重置历史费用。

启动原件 `work/approved-continuations-launch.json`：PID `4053717`，launcher PID `4053713`，SHA256 `5743d4169b90c063a312965a00cdf05f9145faba07e69565716d0f68bdc65fec`。该启动原件指向授权记录 `work/approved-budget-extension.json`，其 SHA256 为 `6018e945c151d28187aaf4f6b228d77cae013cb7e2ff9c3ee9d0abbf5da73cde`。这里记录已有授权和实际账户，不构成新的授权或预算变更。
