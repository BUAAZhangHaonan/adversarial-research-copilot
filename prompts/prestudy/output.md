# 交付当前认识

返回 CandidateCheck，保留原题、已选想法身份与当前 note.decision。以最新 current_understanding 为准，不恢复撤回前提，不把旧初筛意见当作用户要求。

reason 说明这次判断，feasibility 说明进入路径，main_risk 说明最重要的困难，next_question 留给人一个问题。current_understanding 保存剩余核心想法、撤回前提、决定性未知和已有方法的不足。多个字段不要复制同一段论证。

field_updates 仅含新或实质更新的 SourceNote；field_revision 仅替换需要改变的共享章节，其余 null。changes_from_seed 只记录实际变化。没有依据的资源估计留空。交接字段保持完整，读者正文采用共同写作规范，不回放字段和修改历史。
