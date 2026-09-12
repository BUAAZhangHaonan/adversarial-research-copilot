# L4 rendering：两路 compose 协议失败只读复核

核查时间：2026-09-07 08:42:34 UTC。远端 HEAD：`d0d7459d4f68ce80d00598c86fb5676aab2d620c`。仅读取本次运行的 SQLite、已保存响应和源码；没有模型/MCP调用、重试、科研字段修订、进程操作或远端写入。本文不包含 reasoning/COT 正文。

## 结论

- **ARC compose 是输出协议失败。** 首次响应正文为空；一次结构修复后返回合法 JSON，但包含唯一不允许字段 `result.card_candidate.contribution.secondary_types_inline_removed: null`，触发 `extra_forbidden`。当前严格 schema 正确拒绝额外字段；未发现程序误选 schema 或正文组装丢失。不能自动删除该字段后追认为已接受。
- **direct-Pro compose 是真实证据外键失败。** JSON 完整通过 `Envelope[ComposeResult]`，但 `result.card_candidate.claims[1].evidence_ids[0]` 为 `ev_d8ed6484918c8461662beefc`。该 ID 在 evidence 表不存在，也不在当前冻结的 19 个证据 ID 或原请求文本内。这里是科研主张引用，不是可由工具日志派生的执行记录。
- 两个任务均 `accepted_result=null`。本次证明的是具体协议失败原因，不能推断候选科学价值、两路相对质量或 L4 比较已经完成。ARC 修复稿尚未进入后续语义检查，不能声称其全部科研引用和判断都已通过。

## 实际任务、响应与账本

公共 run 前缀：`arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover.comparison`。

| 任务后缀 | 最终状态 | 原因 | 本次 compose 费用，CNY |
|---|---|---|---|
| `.ARC.compose` | PAUSED_PROTOCOL，08:33:08.898033 UTC | INVALID_OUTPUT_AFTER_REPAIR；repair_count=1 | 0.772760–0.772761 |
| `.direct-Pro.compose` | PAUSED_PROTOCOL | unknown_evidence_id；repair_count=0 | 1.264327–1.264328 |

| call_id | 模型 | 开始 / 结算 UTC | 正文字符 | finish_reason | 输入 / 输出 / reasoning tokens |
|---|---|---|---:|---|---|
| `call_c1e38dfa102a49358ef034a194c33cd0` | deepseek-v4-flash | 08:28:28.015760 / 08:29:28.135345 | 0 | stop | 87447 / 6801 / 6801 |
| `call_8fc8ac6d587d497cb74b8266f49c7b88` | deepseek-v4-flash | 08:29:28.230350 / 08:33:08.156530 | 19459 | stop | 87471 / 22900 / 13713 |
| `call_fb640769fda6440a8408fad1ef35ba18` | deepseek-v4-pro | 08:33:10.175456 / 08:39:10.662436 | 15469 | stop | 85741 / 18989 / 12192 |

三次响应的已保存 SDK chunk 正文逐段拼接均与 `response.message.content` 完全相等。首响应共 6803 个 chunk，其正文拼接仍为空；没有正文被 assembler 丢弃的证据。保存对象是 SDK 解析后的 chunk，不是独立 HTTP 抓包。

ARC 首次结构错误为 `json_invalid`（`EOF while parsing a value at line 1 column 0`）。修复稿仅有上述一个 `extra_forbidden`，包含 6 个 claims 和 3 个 hypotheses；不是缺少 claims 字段或整体没有候选正文。direct-Pro 也包含 6 个 claims、3 个 hypotheses；遍历全部证据外键共 19 次引用、13 个不同 ID，仅上述 ID 不存在。

## 可复核原件与哈希

以下路径相对于 `/home/g203/zhanghaonan/adversarial-research-copilot/.arc-validation/artifacts/`。

ARC 任务目录 A：
`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover.comparison.ARC/tasks/7b8b076376cfa3cb52947c8636fdac762d9e5a8205e516810354af4e31d86f62/`

direct-Pro 任务目录 P：
`runs/arc-vnext-validation-20260907.ARC_RENDERING_VALIDATION.discover.comparison.direct-Pro/tasks/c0eae1f259fbc2ec3d7865616122414dd29630623b20dbebd0eb78d67be77e25/`

| 目录与文件 | SHA256 |
|---|---|
| A `states/b971de16a822443e9a9e7f773c619f1f.json`，首响应 | `ef519cc5f34bbd524787fc668df4738731b41171e7603c17f21ee437657008f5` |
| A `states/4589311769dc40678f391cf5aa166699.json`，修复响应 | `7a0568ed8a9cf8f5c6fed51e340ae189b2cf1507054994df4744e863b138e388` |
| A `states/bad0c06d6b9d4ff08a9ae5a11ad0167a.json`，最终暂停状态 | `090ac29657b437bdeb5a4fa1b968149e77d364b8be8beb4dd9299476ca64f9f3` |
| A `requests/call_8fc8ac6d587d497cb74b8266f49c7b88.json` | `af472207456f24dbba71040cdfd13ee526f44174561e524261aef8ac7a2c7ae2` |
| P `states/70d2bacd36c24dd7903b80c23ac49da3.json`，响应 | `181f7c953a6a1a3a016c2d4b60403668f24fa74fe3bc10590661e89c4c353135` |
| P `states/2308d47382fd4b6e81b215533ccbfef3.json`，最终暂停状态 | `9482c815b231cc3a0d2e960f3bf02a7549d6219d25819a2d8af3349c1cde70db` |
| P `requests/call_fb640769fda6440a8408fad1ef35ba18.json` | `27f6f627a8806a7ccd321dba1ce81097d056d5939b6ef8d466cf4324ccd3dfe9` |

正文 UTF-8 SHA256：ARC 首次为空字符串 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`；ARC 修复稿 `905fecc19b6bbf3f09e840c8c4ebf8ec9a190730c821c2e93c19cd583bf8c4c9`；direct-Pro `506075ae79a22ccd6b0cb15c4eea3f0b1483af1a8e422e5158ac7632119076b5`。

## 校验依据与复现范围

使用远端当前 `.venv/bin/python` 对保存的正文执行 `Envelope[ComposeResult].model_validate_json`，未创建 Runtime、Store 实例或调用外部服务。SQLite 使用 `mode=ro`。对 direct-Pro 按结构化证据引用键遍历并查询 `evidence.id`，同时核对任务冻结 `evidence_ids` 和请求原件。

代码依据：`src/arc/schemas.py:15` 的 `extra="forbid"`；`:103` 的 Contribution 仅定义契约字段；`:453` 的 ComposeResult；`src/arc/evaluation.py:71` 按角色/任务选 schema，`:165` 两路同用 COMPOSE；`src/arc/runtime.py` 的结构解析和一次修复边界；`src/arc/store.py:710` 的未知 evidence 拒绝。

核查时源码 SHA256：schemas `4fb98e0c01b1ec65af38acd3645a03218eebbdcf29584759ddd0098af1c27fbd`；runtime `5a86af48ca62a30ce3ce5fdb57780703112fe2cf6bd53678471971be5c69273a`；evaluation `adaf843fcabae1c8acc5672e8373915093e6792b9fdc4ca7032ee27af70e4eec`；store `5b0c79b92491a95e22d4202929fa3d58053a59659f9ac001f3435f2f958357a0`。
