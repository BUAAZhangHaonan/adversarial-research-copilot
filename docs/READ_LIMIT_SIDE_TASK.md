# 能力与改进需求

需求：cap_arc-vnext-validation-20260907.natural_tool_correction_v1.develop.user.64k.review

运行：arc-vnext-validation-20260907.natural_tool_correction_v1.develop

来源任务：人工登记

状态：reviewed

## 原始需求

{
  "blocked_question": "原文分页读取多次越界，是否应为后续任务提高单次读取长度？",
  "needed_operation": "read_record",
  "input_fields": [
    "record_id",
    "version",
    "offset",
    "limit"
  ],
  "required_output": "原文片段及原有分页覆盖元数据",
  "provenance_needs": "保留来源、版本和字符offset，原始全文不改",
  "cost_visibility_needs": "本地读取本身免费，但更大的输入需计入下一模型请求；沿用原准入和费用上限",
  "acceptance_example": "候选新版本允许limit=64000字符，64001仍拒绝；分页内容及来源不变",
  "current_limitation": "g203 master公开上限为24000字符；此前develop请求30000、run请求52265均在执行前被拒绝",
  "proposed_change": "为未来的新任务独立验证64000字符单页上限；当前运行不改配置",
  "rationale": "用户提出64K作为改进示例。合法分页已能读取全文，扩大单页可能减少交互次数，但不能替代参数纠正机制",
  "alternatives": [
    "保留24000字符，以offset分页加一次协议纠正：无需容量调整，但长文可能多次交互",
    "在新的验证任务中试验64000字符：可能减少模型往返，但单次输入更大，需测量总费用与延迟"
  ],
  "expected_impact": "可行性来自当前本地字符串切片实现；实际时延、token和质量收益尚未测量，不能先声称更便宜或更好"
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
    "仅修改read_record公开schema及对应Markdown上限、边界测试；不把64000字符混同为64K tokens，不放宽其他工具",
    "在新任务中使用新schema；保留旧任务和失败原件，依赖变化不通过手工修改检查点绕过",
    "不增加预算，不改模型或服务，不自动创建任务；新付费对照的额度与使用账本由用户在执行时明确"
  ],
  "rationale": "已检查src/arc/runtime.py build_tools：read_record是本地Store读取及字符串切片，24000来自公开schema；64000字符没有结构性实现障碍。相比保持24000分页，可能减少往返但增加单次上下文，实际token数取决于文本。推荐作为未来独立支线进行对照验收；本轮先保持24000，验证纠正路径。只改上限不能解决其他协议错误，也不能重用旧冻结schema任务冒充续跑。",
  "recommended_option": "在用户选择执行后，为新任务验证64000字符单页读取；达到成本、分页和恢复验收后再采用。当前master及正在运行任务保持24000。",
  "validation_plan": [
    "离线核对24000与64000返回同一原文窗口，offset/version/来源元数据不变，64001在执行前拒绝且保留一次纠正机制",
    "新增一次性测试任务覆盖正常分页、预算暂停及恢复不重放；旧冻结任务仍明确报告schema变化",
    "使用用户批准的同一材料和预算对比模型调用数、输入token、耗时及费用；若收益不明确则保留24000"
  ]
}


## 用户执行支线交付模板

用户决定采用后，可将以下文本交给 CodeX；本文件没有创建或启动任何任务。

基于需求 cap_arc-vnext-validation-20260907.natural_tool_correction_v1.develop.user.64k.review，请实施已评估选项：在用户选择执行后，为新任务验证64000字符单页读取；达到成本、分页和恢复验收后再采用。当前master及正在运行任务保持24000。

实施范围：


- 仅修改read_record公开schema及对应Markdown上限、边界测试；不把64000字符混同为64K tokens，不放宽其他工具

- 在新任务中使用新schema；保留旧任务和失败原件，依赖变化不通过手工修改检查点绕过

- 不增加预算，不改模型或服务，不自动创建任务；新付费对照的额度与使用账本由用户在执行时明确


完成验证：


- 离线核对24000与64000返回同一原文窗口，offset/version/来源元数据不变，64001在执行前拒绝且保留一次纠正机制

- 新增一次性测试任务覆盖正常分页、预算暂停及恢复不重放；旧冻结任务仍明确报告schema变化

- 使用用户批准的同一材料和预算对比模型调用数、输入token、耗时及费用；若收益不明确则保留24000


交付修改文件、验证结果及未完成项。保留原研究记录；不得把能力改善当成科研证据。



登记、评估和导出均不授权安装工具、修改服务、放宽工具限制或增加预算。
实际执行前，由用户明确选择执行范围；涉及新增费用或服务权限时单独取得授权。
