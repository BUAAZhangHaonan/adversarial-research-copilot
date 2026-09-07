# 协议改进后的自然卡复验

2026-09-07，使用已自然discover并被selector选为MAIN_REPORT的 `card_52bce58017164c2b9594c418eb0cac7b` v1。CodeX选择它进入后续验证，因为其问题与最小检验可明确讨论，尚未确认的轴独立性和测试GT覆盖假设仍应受到质疑。未启动实验或论文任务。

## 结果

运行 `arc-vnext-validation-20260907.natural_tool_correction_v1.develop` 在源码 `21b0cd2` 下完成来源复核及一个合法的developer响应，最终仍为 **PAUSED_PROTOCOL / changed_claim_requires_new_version**。卡版本提交前的依赖检查拒绝该修订，原卡保持v1；新run阶段未启动。不能把TaskRecord的ACCEPTED响应状态等同于develop阶段完成。

两个任务分别用了自己的一次最终JSON结构修复。来源复核有28次成功工具调用，developer有4次；本轮没有越界工具调用，因此真实运行没有触发工具参数纠正。该分支的成功/失败/中断恢复证据来自21项离线协议测试，不宣称已在自然真实调用中命中。

developer首稿 `call_a8979db48b9845a88fe68c6a91ec5d62` 的JSON解析报 `trailing characters at line 1 column 54235`。一次修复 `call_5b9d5147d14042778d566ff3058b38d5` 返回通过结构解析的对象。其affected_claims与三条实际变化claim对应，但下列一条版本不合法：

| claim | 变化字段 | 原版本 | 提议版本 |
|---|---|---:|---:|
| claim_d1c_default_confound | conditions | 1 | 2 |
| claim_d1c_gap_logical | text、conditions | 1 | 2 |
| claim_d1c_measurement_ambiguity | conditions | 1 | 1 |

`Store.validate_claim_dependencies`要求text、conditions或kind变化时递增claim.version。这项检查防止旧目标证据被误用，不能删除。developer提示词却把runtime创建卡ID/版本和模型应提出合法claim版本笼统放在一起；需要澄清责任。不是无法修复，也不是费用问题。

## 已登记的改进与选项

CodeX已把本次具体失败登记为来源于development任务的改进需求，并记录两种方案的评估；它不是DeepSeek主动提出的建议。

推荐先澄清Markdown中的卡/claim版本规则，同步核对evidence_review和旧目标证据，再在明确的新运行版本验证。备选为runtime统一分配claim版本，但需要同时调整证据依赖与事务，改动范围更大。两者均未在本轮执行，详见[版本协议优先支线](CLAIM_VERSION_SIDE_TASK.md)。

[64000字符读取支线](READ_LIMIT_SIDE_TASK.md)是另一个已评估但未执行的选项，不能修复本次claim版本错误。当前上限仍为24000字符。评估与交付不会自动扩大权限或费用，也不会自动创建任务。

## 费用与证据

本轮28次模型请求、32次工具调用，共60条账目；费用1.679891–1.679914元。原100元父账本累计46.833939–46.983457元，剩余53.016543元，预留0、未知调用0。没有清空旧费用或重新授权100元，也没有继续重试已耗尽纠正额度的任务。

私有原件根目录为 `/home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation`。汇总审计为 `artifacts/evaluations/tool-correction-20260907-result.json`；原始响应、纠正请求与状态均在 `artifacts/runs/<run_id>/tasks/`，未改写或发布private reasoning。

本轮启动脚本、日志、结果位于g203主仓库 `work/live_tool_correction_validation.py`、`work/tool-correction-live.log`、`work/tool-correction-validation-result.json`。已重建本轮REPORT及MCP_REQUIREMENTS，包含两项已评估需求。真实L3仍未贯穿，原L4三组比较仍未完成，最终总验收尚未通过。
