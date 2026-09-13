# 整理当前预研报告

任务类型：{{ task_type }}
任务标识：{{ task_id }}

依据以下已保存材料，写给研究同事阅读。使用当前认识与给定来源，不开展新调查。

{{ payload_json }}

返回下列 schema 的 JSON。自然语言字段只写正文；候选状态由原记录控制。表达整理完成时 result_status="complete"、evidence_requests=[]，研究中尚未知的内容如实保留。

{{ output_schema_json }}
