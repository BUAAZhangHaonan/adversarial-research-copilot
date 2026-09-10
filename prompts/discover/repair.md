# 修正本次 JSON 输出格式

任务标识：{{ task_id }}

原任务资料：
{{ payload_json }}

上一份输出：
{{ previous_response_json }}

结构诊断：
{{ validation_errors_json }}

要求的 JSON 结构：
{{ output_schema_json }}

仅修正诊断中的格式或引用指向。保留原始候选、实质判断及不确定性；不能为了通过校验增加实验、改变问题、编造来源或把缺证改成已证。不执行新检索，实质内容缺失时不虚构通过结果。

若诊断为unknown_source_id：从reference_directory与已成功工具记录复制同一来源的内部source_id，不能原样保留arxiv编号或URL，也不能只改正文。不确定具体记录时保留待查与访问限制，不编造编号或将摘要升级为全文。
