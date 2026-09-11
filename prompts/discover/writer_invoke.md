# 最终中文报告润色

任务：{{ task_type }}；任务标识：{{ task_id }}。

以下是已保存的技术内容、原判断与唯一可用来源目录。只整理这些内容的表达：

{{ payload_json }}

完成表达整理后，Envelope.result_status使用"complete"、evidence_requests使用[]。这不改变候选的原判断，也不表示证据缺口已解决；未知与限制保留在正文中。

仅返回符合以下结构的JSON：

{{ output_schema_json }}
