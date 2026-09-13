# 修正报告输出

任务标识：{{ task_id }}

本次任务对象（按此复制 subject，材料中的历史运行编号不是本次任务身份）：
{{ subject_json }}

原始材料：
{{ payload_json }}

上一份输出：
{{ previous_response_json }}

本次诊断：
{{ validation_errors_json }}

要求的结构：
{{ output_schema_json }}

修正被指出的 JSON、候选覆盖、引用、任务状态或长度问题，返回完整对象。遇到长度问题，先删重复内容和非必要背景，再重新组织段落；不能只插入空行，也不能截断句子、删去决定性条件或改动研究判断。

保持原题、当前事实、范围、未知和来源关系。不新增研究或事实，不把缺失材料写成已取得。正文能够忠实整理时使用 result_status="complete"、evidence_requests=[]。不要在正文解释这次修复。
