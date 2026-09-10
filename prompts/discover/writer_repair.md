# 修正本次润色 JSON

任务标识：{{ task_id }}

原始技术内容与来源边界：
{{ payload_json }}

上一份输出：
{{ previous_response_json }}

诊断：
{{ validation_errors_json }}

要求的JSON结构：
{{ output_schema_json }}

仅修正格式、候选覆盖、引用指向。保留原研究对象、判断、条件与未知，不开展检索或科学复审，不以新事实填空。恢复输入允许的表达后返回完整对象。
