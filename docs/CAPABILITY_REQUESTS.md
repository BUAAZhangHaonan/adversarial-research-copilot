# 能力与改进需求

科研任务可用 `request_capability` 记录缺失能力或已有工具的改进提议。
例如，任务可以提出评估 `read_record` 的 64000 字符单页上限；登记不会改变当前上限。
任务也可在结构化响应的 `capability_requests` 中声明需求。两条路径都保留来源任务，
并进入 `pending_user_review`。正式 Agent 只提需求，由用户评估并决定实施。
科研报告的 `MCP_REQUIREMENTS.md` 汇总需求与评估；正式运行不依赖 CodeX。

需求必须写明原问题、所需操作与输入输出、原文追溯要求、费用可见性、验收例子，
以及当前限制、具体建议、理由、现有替代方案和预期影响。当前限制应来自实际观察。

1. 用 `arc --data-dir .arc requirements list RUN_ID` 查看需求。
2. 用 `arc --data-dir .arc requirements export REQUEST_ID --output review-handoff.md`
   导出用户评估模板；命令本身不创建任务或调用模型。
3. 用户核对相关实现并比较方案后，写出以下结构的评估 JSON，再用
   `arc --data-dir .arc requirements review REQUEST_ID --review review.json` 登记。
4. 再次导出同一需求。如果评估推荐实施，文件会附用户执行支线模板，列出选项、范围和验证。
   用户选择是否执行；研究流程不会因建议记录而扩大权限。

```json
{
  "assessment": "recommended",
  "rationale": "分别说明候选方案和保持现状的优点、缺点、成本及尚未确认的影响，不仅复述需求方替代方案。",
  "recommended_option": "给出具体推荐选项。",
  "implementation_scope": ["列出最小修改范围。"],
  "validation_plan": ["列出可执行验收，包括原有限制和预算边界。"]
}
```

`assessment` 也可为 `needs_information` 或 `not_recommended`；没有推荐选项时
`recommended_option` 为 `null`。这两种评估不生成执行支线。评估记录不能原地替换；
若研究条件改变，可登记明确说明新情况的新需求。重复提交同一评估不会新增记录。

只有开发阶段需要 CodeX 参与时，才显式导出开发评估模板：

```text
arc --data-dir .arc requirements export REQUEST_ID --development-review --output development-review.md
arc --data-dir .arc requirements review REQUEST_ID --review review.json --reviewer codex --development-review
```

这两个命令也不调用 CodeX。第二条命令只登记已提供的开发评估，保存 `reviewer=codex`、
`review_context=development`。默认登记为用户评估，保存 `reviewer=user`、
`review_context=production`。未显式选择开发阶段时，不能把 CodeX 登记为评估者。
旧 `pending_codex_review` 状态和旧评估保持原记录可读，不自动改写；缺失的评估者不会被补造。

人工需求可用 `arc --data-dir .arc requirements add RUN_ID --request request.json` 登记，
输入遵循 `CapabilityRequest` 的字段定义。原始需求保留，评估只增加评估信息。
登记、评估和导出均不安装工具、不改变服务、不放宽上限、不增加预算，也不声称建议具有科研证据效力。
