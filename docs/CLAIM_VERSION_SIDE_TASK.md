# 能力与改进需求

需求：cap_arc-vnext-validation-20260907.natural_tool_correction_v1.develop.codex.claim-version-review

运行：arc-vnext-validation-20260907.natural_tool_correction_v1.develop

来源任务：arc-vnext-validation-20260907.natural_tool_correction_v1.develop.development

状态：reviewed

## 原始需求

{
  "blocked_question": "develop修复JSON后仍因一个改写conditions的claim未递增版本而暂停，如何减少版本协议失误？",
  "needed_operation": "developer claim revision contract",
  "input_fields": [
    "original card claims",
    "proposed_revision.claims",
    "affected_claims",
    "evidence_review"
  ],
  "required_output": "保留科研文本、正确表达claim版本和证据依赖的方案修订",
  "provenance_needs": "原卡v1和失败原文保留；不得把旧claim证据自动升级为新claim支持",
  "cost_visibility_needs": "当前任务已经用完一次纠正；新版本验证仍须计入原100元父账本，不重置费用",
  "acceptance_example": "claim_d1c_measurement_ambiguity的conditions变化时提出递增版本，并使evidence_review对应相同版本；未改变claim不无故递增",
  "current_limitation": "Store按text/conditions/kind变化强制递增claim.version；developer.md却笼统说runtime创建IDs和versions，没有明确卡版本与claim版本的责任区别。当前两条变化claim正确提出v2，另一条conditions变化仍为v1，导致changed_claim_requires_new_version",
  "proposed_change": "澄清claim版本及同目标旧证据的修订协议，在明确的新运行版本中验证；本次不改旧输出",
  "rationale": "CodeX在真实失败后登记此需求；这不是DeepSeek主动提出的需求，也不是预算问题。JSON修复已成功，问题位于后续卡版本依赖校验",
  "alternatives": [
    "先补齐Markdown职责：改动text/conditions/kind必须递增claim.version，review对应新版本，旧目标证据重新核对；改动范围小且保留现有严格校验",
    "把claim版本完全改由runtime分配：长期职责更集中，但必须同步处理evidence_review、目标证据失效和卡事务，需要较大的独立设计与回归"
  ],
  "expected_impact": "减少可避免的版本元数据失误；不能保证模型之后所有科研输出通过，也不能把旧任务修复额度追加为无限重试"
}

## CodeX 评估交付模板

请核对上述实际限制与相关实现，评估提议是否合理，比较当前替代方案，推荐最小可行选项。
将评估写为 JSON，字段为 assessment（recommended / needs_information / not_recommended）、
rationale、recommended_option（无建议时为 null）、implementation_scope（列表）、validation_plan（列表）。
本步骤仅评估，不执行变更。用 arc requirements review 记录评估。


## 已记录的 CodeX 评估

{
  "assessment": "recommended",
  "implementation_scope": [
    "明确runtime分配ResearchCard版本，而当前接口要求developer提出合法Claim版本：text、conditions或kind变化时递增；同时对应evidence_review",
    "说明修改claim后同一claim旧版本的目标证据不能原样继承；需要重新核对，不自动改为新版本证据",
    "保留旧失败及JSON修复记录；不手动改accepted_result、不重置次数；在原100元父账本下验证新的运行版本"
  ],
  "rationale": "已逐项核对最终响应：3条claim变化，其中default_confound与gap_logical提出v2，measurement_ambiguity仅改变conditions但仍v1。现有校验正确保护证据版本；提示词的runtime负责versions表述过宽。推荐先澄清职责并在新版本复验，避免在本轮手工改写模型输出。原claim v1仍完整，run尚未启动。",
  "recommended_option": "优先实施Markdown协议澄清和版本边界回归，然后显式新建运行版本复验；保留现有版本/证据校验。",
  "validation_plan": [
    "离线覆盖仅conditions变化且未递增被拒、合法递增、未变化保留版本、review与证据版本不匹配被拒",
    "检查Markdown不再把卡版本与claim版本职责混为一谈，完整测试通过",
    "新任务验证同一自然卡；记录最终状态、实际费用、仍未解决的协议问题。若develop未完成，不把run标成通过"
  ]
}


## 用户执行支线交付模板

用户决定采用后，可将以下文本交给 CodeX；本文件没有创建或启动任何任务。

基于需求 cap_arc-vnext-validation-20260907.natural_tool_correction_v1.develop.codex.claim-version-review，请实施已评估选项：优先实施Markdown协议澄清和版本边界回归，然后显式新建运行版本复验；保留现有版本/证据校验。

实施范围：


- 明确runtime分配ResearchCard版本，而当前接口要求developer提出合法Claim版本：text、conditions或kind变化时递增；同时对应evidence_review

- 说明修改claim后同一claim旧版本的目标证据不能原样继承；需要重新核对，不自动改为新版本证据

- 保留旧失败及JSON修复记录；不手动改accepted_result、不重置次数；在原100元父账本下验证新的运行版本


完成验证：


- 离线覆盖仅conditions变化且未递增被拒、合法递增、未变化保留版本、review与证据版本不匹配被拒

- 检查Markdown不再把卡版本与claim版本职责混为一谈，完整测试通过

- 新任务验证同一自然卡；记录最终状态、实际费用、仍未解决的协议问题。若develop未完成，不把run标成通过


交付修改文件、验证结果及未完成项。保留原研究记录；不得把能力改善当成科研证据。



登记、评估和导出均不授权安装工具、修改服务、放宽工具限制或增加预算。
实际执行前，由用户明确选择执行范围；涉及新增费用或服务权限时单独取得授权。
