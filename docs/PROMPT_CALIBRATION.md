# Investigator 开发案例校准记录

日期：2026-09-07。只依据已发生的 V2 开发调查失败修改；没有使用留出主题，没有新增付费调用，没有修改 V2 的 accepted 对象或原始响应。

## 失败对象与原件

- task：`arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V2.discover.shared_investigation`。
- 读取位置：g203 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation/arc.sqlite` 的 `tasks.data.accepted_result.result`。当时 TaskRecord 状态为 `ACCEPTED`，但后续证据登记失败；角色输出已保存不代表科研证据合格。
- 原 rendered prompt hash：`8adc9a1bece0b8d33d2e9e73ff850a5a2fda48e6ca9a8733cb46a57839b57be7`。
- 原 role 文本 SHA256：`7b412a9eb3aea6f245fa5fd9e8971689fb2835e74cf27b0d29292641e5b6811f`。

原件相对于该数据目录的 `artifacts/`：

```text
runs/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V2.discover/tasks/a4ccc3cbf7dba1664e6266ffa0011e62ebf79c6a25ce62c6e452c4b4cb10b6ae/prompt.json
runs/arc-vnext-validation-20260907.ARC_VNEXT_VALIDATION_V2.discover/tasks/a4ccc3cbf7dba1664e6266ffa0011e62ebf79c6a25ce62c6e452c4b4cb10b6ae/states/22eeb78913a74501b2e3e2b723e85268.json
```

第二个文件包含 `response.message`、原始 chunks、messages 和 tool_trace；其本次只读核对 SHA256 为 `bc3a0513e256f6cfebfbe10b9c652ec375825f0280034ae3588f051c71425fba`。不将原始 reasoning 复制进本说明。

## 引用失败分类

逐条读了13条 findings 和2条 contrary_findings，并与当前 source registry 指向的保存正文比较。仅 findings[8]、findings[9] 的 excerpt 是对应正文的精确连续子串。其余13条不是空白归一化问题，也没有据此发现跨论文误引。以下索引均从0开始；类别描述来自逐条字符核对，不作为科学真假标签。

| 位置 | 失败类别 |
|---|---|
| findings[0]/[1]/[3]/[4]/[7]、contrary_findings[0] | 把同一来源多个不同位置的片段用 `...` 拼成单个 excerpt。 |
| findings[2] | 多段拼接，同时改写大小写和部分措辞。 |
| findings[6] | 多段拼接，改变句首大小写，并删除引用标记。 |
| findings[10] | 多段拼接，省去原文的 `[23]` 引文。 |
| findings[12] | 多段拼接，将抽取正文中的数学表示改为排版后的 `40×`。 |
| contrary_findings[1] | 把原词 evaluations 改为 experiments，并在 excerpt 内加入自己的括号概括。 |
| findings[5] | `src_ca8679aeb9914d9699498053ee3cda41` 只有 metadata、无 content_path，却以 origin=original 提交搜索片段；来源不可访问也不能把片段变成原文。 |
| findings[11] | `src_22ab2dfccd8546968d3071dc40fbc74a` 同为 metadata、无 content_path；origin=secondary_analysis 也不能把搜索结果变成二级研究分析，excerpt 还改了片段标点。 |

两条metadata片段分别来自成功搜索 `tool_aa79b5363a7440cdae6b2a0623a041a1`、`tool_7c6960b7d7b64fffb953732be7ea6355`。正文或片段本身曾经返回，不等于模型重组后的引用仍能按原文核对。

## 科学范围错误

[SOURCE_SPOTCHECK](SOURCE_SPOTCHECK.md) 保存原文source ID、hash和具体行/字符范围。该独立核对发现：

- findings[0] 从某节没有专门合并扰动分析，扩大成任何 AP/PQ 层面都未测试；findings[1] 将单掩码内部反例推广为合并的共享边界必然不可见，遗漏真值边界带、实例匹配和实际组合指标的前提。
- contrary_findings[0] 将一个合成实验的聚合数值相等扩大为所有小目标的结论；findings[6]、contrary_findings[1] 从对象数量推断密度，并把“已读材料未看到类型分解”扩大为仅有聚合证据。
- 已存正文的version为null，不能从另一个摘要网页的最新修订号把正文补成v5。

这些是对已读原文支持范围的检查。它们既不证明待研究方向一定成立，也不构成对尚未生成研究卡的否决。

## V2之后的调查提示词改动及理由

仅在 `prompts/roles/investigator.md` 末尾追加 `Exact excerpts, source access and claim scope` 小节；追加前的全文按上述原role hash逐字保留。

追加后的role SHA256：`f32ea22469f09f915fb089d0c88bf86df2cfd9eb769b457924d10f90ec1acaa0`。这是一份新提示词资产；V2 task仍指向旧hash。

| 追加规则 | 对应失败与目的 |
|---|---|
| 单个excerpt只复制连续原文，保留大小写、符号、引文与返回的数学格式；多段分开finding | 防止拼接与改写伪装成可验证引文；解释留在claim/support_explanation。 |
| metadata/snippet只是线索；缺正文放入access limits或未决问题，作者摘要只支持其自身陈述 | 防止来源层级升级；不因链接权威或网页版本号就宣称读过完整原文。 |
| 事实停在所测条件与分析层级；跨协议/数据/几何等外推单独标inference并说明前提 | 防止有限未发现变成全文/全领域否定，或聚合观察变成逐实例普遍命题。 |
| 三个短的通用反例 | 只示范大小写/引文变更、跨段拼接、单设置到全设置的错误；不写论文标题黑名单，不改变科研品味或任务主题。 |

## 校验与后续对照

提示词测试检查原全文hash前缀保持不变，并在 investigator.INVOKE 与 investigator.SCOPE_AUDIT 的实际渲染system中检查新规则和通用反例可见。它只证明规则已送入提示词，不能证明模型一定遵守。

本次离线运行 `pytest tests/test_prompts.py`：17 passed；`git diff --check`通过。未运行真实V3，未发起付费补查。

代码侧的证据预校验由主线程负责，不能靠提示词替代。V2原件保持不动；主线程将使用明确的新V3 run复用已有原始材料验证，沿用原100元父账本。留出主题尚未运行，不用于本次调参。V3结果、费用及是否改善需在真实运行后另行补记；本记录不提前宣称质量提升。

## V3之后：补证请求归属说明

V3已保存card_106f9f81b76c449cb429c4c883dbeb1d v1。其draw1.novelty首先返回非JSON，单次结构修复后仍违反已有卡的EvidenceRequest契约：req_array_2025的claim_id、issue_id、draw_id全为null。离线重解析复现evidence_request_requires_subject；该任务保持PAUSED_PROTOCOL/INVALID_OUTPUT_AFTER_REPAIR，accepted_result=null，不人工补ID、不追加第二次修复。状态原件后缀为tasks/5c0d21efd3b1667b2f500002524edc9308794b4dddfefd3af7f864fd4dc38e6f/states/34930a4eddb447d0a9ad0827b1f5ce95.json。

只在common/output_protocol.md末尾追加Evidence request ownership通用说明，原模板完整保留：已有卡的请求必须复制当前输入中相关的claim/issue/draw ID，nullable字段不代表三者都能为空；前卡尚无这些实体时才由实际task/run归属。不得编造ID，也不把卡片级subject替代请求级关联。未改变schema、判断标准或原有失败记录；没有加入案例标题或领域词黑名单。

该公共资产SHA256：追加前76a264e10bbad00f9ce7694f5d7ee4a4773115ca6e7b192da835904b12142ac4；追加后99e1f8839135d599dfba0a47056a0f52463e2a9e6f4f85f3f8b3bd8a63202d8e。其原文前缀和所有语义角色的实际渲染已纳入测试；包含本改动及L4边界/种子修复的整套离线检查为258 passed / 46.23s，日志work/tests-evaluation-ownership.log。

这是基于开发题目的协议校准，后续用明确标记的独立L2输入和固定材料对照验证。它不让原V3自动通过，也不证明模型科研判断已改善。原卡及被拒novelty中的实质问题见V3_EVIDENCE_REVIEW.md，未注入本次提示词。未使用holdout调参。
