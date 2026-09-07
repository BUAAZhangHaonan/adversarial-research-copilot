# L4 holdout ARC：证据请求归属失败只读复核

核查时间：2026-09-07 09:03:27 UTC。远端 HEAD：`8cbc650ad1caf24ca077ba21e35e445e4f14531b`。范围仅限已结束的 holdout ARC compose；没有读取或干预仍在运行的 direct-Pro，没有模型/MCP调用、重试、代码/提示词或科研结果修改。

## 结论

这次是**新候选的局部 claim ID 被当作当前输入已提供目标使用**。该 ID 在同一响应的新候选中确有定义，不应笼统称为毫无对应实体的幻觉 ID。当前实现明确要求每个非空请求 claim/issue/draw ID 来自冻结输入，因而按既定规则拒绝；没有发现匹配算法遗漏了输入已有目标。

任务书 B1（`EXECUTION_SPEC.md:1091`）要求请求关联 claim/issue 或当前 draw，并提供问题、来源/查询、用途和决策后果，但没有明确细化“同一响应中新候选局部 ID”的作用域。已实现的冻结输入规则更具体；无卡阶段已有三个 ID 全 null、绑定实际 run/task 的合法方式。因此这不是前置阶段没有任何合法表达方式的结构性死路。该 holdout 结果保留为当前协议下的绑定失败，不据此修改协议、提示词或原结果，也不能追认为科学接受成功。

## 实际错误与输入目标

- Run：`arc-vnext-validation-20260907.materials.conflict_holdout.comparison.ARC`。
- Task：上述 run 加 `.compose`；`PAUSED_PROTOCOL / evidence_request_claim_id_not_supplied_to_task`，09:01:37.667625 UTC；`repair_count=0`。
- Response：`result_status=complete`；`Envelope[ComposeResult].model_validate_json` 完整通过。17151 字符正文，`finish_reason=stop`。
- 唯一请求：`req_annotator_reliability_literature`。`claim_id=claim_proto_004`，`issue_id=null`、`draw_id=null`。
- `claim_proto_004@1` 是 `result.card_candidate.claims[3]`，属于同一响应新创建的五条 `claim_proto_001`–`005`。该主张限定为：已核验材料未建立同一受控设计下双轴分级操纵可靠性和歧义度的结论，仍受检索与全文边界约束。请求意图是继续核查对应最近工作缺口。
- 输入只有 `approved_family/boundaries/evidence/sources/topic`；subject 的 card、campaign 均为空，仅有真实 run。没有输入 card、issue 或 draw。`claim_proto_004` 不在其中。

当前 `reference_ids(payload, {'claim_id','claim_ids'})` 在输入的 EvidenceRecord 中可见以下 15 个已有 claim ID；这些是检索材料关联主张，不是本次尚未接受的新候选 ID：

```text
claim_0ba3bf12e30894c18f01a972
claim_2288cc76c2b8ec28cd100cc6
claim_2b3566b1f05734ee37912187
claim_2f4ce9e9d0a43b2b36fa440b
claim_3983eb45a5fd149c85bfb8c8
claim_4e8f603f59e07b16f0d1b853
claim_508dcf89f344c7a9d15cf749
claim_7236c5fb30350641a7c37962
claim_8b974ae3d7120852c95dc718
claim_a343778c3a4590d041b4e6e3
claim_aa7cfc4ac75f44d5839061d9
claim_b3589c5f12fd5470de4a8f34
claim_c76e901a01733e8cee119590
claim_e55e550b27408e40f732235e
claim_f7b5aa3b92dae70e3de54c48
```

本次没有建议把请求随意改绑这些背景 claim；可见不等于科学上相关。输入 issue/draw ID 集合都为空。

请求的六个 `target_source_ids` 均在冻结输入且已登记为 `retrieved/original`，所以报错不是这些来源 ID 不存在：

| source_id | 登记 canonical_id |
|---|---|
| `src_a52b6f2fd0764172bd63388670d068d6` | `arxiv:2602.09214` |
| `src_2bc0d3af90fd467f8658dfefccfce2f8` | `https://icml.cc/virtual/2026/79619` |
| `src_ab14012376ac48009cc2499da3bae672` | `https://openaccess.thecvf.com/content/CVPR2026F/html/Popordanoska_CLASH_A_Benchmark_for_Cross-Modal_Contradiction_Detection_CVPRF_2026_paper.html` |
| `src_308707369e4c4307977a8cde702a4c99` | `https://aclanthology.org/2025.findings-acl.1037` |
| `src_03f5a98c9f024b42a848c3175792d7ae` | `https://aclanthology.org/2025.findings-ijcnlp.124` |
| `src_8fb4ee90c6c344d5a5e6f32482edff9f` | `arxiv:2509.02805` |

这张表只证明已存来源身份和输入可见性，没有访问这些网页或重新审定文献内容。

## 调用、原件与校验依据

调用 `call_17820b127b1d4bf2a2824cbbfbe0a9e6` 已 SETTLED：08:58:13.069641 开始，09:01:37.493999 UTC 结算；费用 **0.234507–0.234508 CNY**，直接引用原账本。

下面路径相对于 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation/artifacts/`。公共目录：

`runs/arc-vnext-validation-20260907.materials.conflict_holdout.comparison.ARC/tasks/ab9bd003598c121ca34c1dc554983b6996e3e9b6616938d8b70215501402aeb6/`

| 原件 | 实际读取字节 SHA256 |
|---|---|
| `prompt.json` | `d16b7fb01f8c6746fce4301e45c537f98bdfc9f7a898f4eeb34da02aaf67e15a` |
| `requests/call_17820b127b1d4bf2a2824cbbfbe0a9e6.json` | `ca2457de070058b2da494dd255945ae1bb7a04fe89b694f6b8055d31457aa5d6` |
| `states/0e40a4eba9534ddd9df4215ea8bd972d.json`，已保存响应 | `fd9463e9bfba5c0f2b91f88a14c8f0a1761e30426db37adca4df0c6827544c19` |
| `states/0bfebca37cf04b33a25ab2350edadec4.json`，最终暂停状态 | `4813cb4c3efd66bba2c48a5307c197bd4771aae501a1b8d4436bfab11ab85397` |

响应正文 UTF-8 SHA256：`d97487aa7904e94188477d87f1e4e5711542647e22ab3f02dabd63f82ae8a37b`。

从保存的 prompt 解析冻结 payload/subject，并用当前 `Envelope[ComposeResult]` schema 重算 input hash，结果精确匹配 TaskRecord，排除本次取错上下文或 schema。实际 prompt 已包含 `Evidence request ownership` 小节：既有卡目标来自当前输入，无卡时允许 task/run 作用域的空目标。当前 `runtime._validate_semantics` 对三个非空 ID 分别检查冻结 payload；`schemas.Envelope.completion_contract` 处理前卡空目标。`evaluation._frozen_call` 不在线扩展证据请求，持有未接受候选不能绕过此校验。

本次只作协议审计，不展示 reasoning/COT；不声称已验证请求所述文献缺口或卡片新颖性。
