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

若来源访问级别不匹配：一次修正全部错误。retrieved_source_catalog列出本任务实际可见的记录，同一论文的检索记录与已读取正文可能有不同source_id。只在能确认同一论文和版本时把引用指向实际读取的记录；没有对应正文时保留元数据/摘要限制，局部正文用passage。目录仅证明材料可用，不代表它支持当前判断。
