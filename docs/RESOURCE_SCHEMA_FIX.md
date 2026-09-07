# 资源估计 schema 可见性修复

本修复来自开发输入的真实失败，原件和错误分层见[L2导入审计](L2_SCHEMA_FORK_PROTOCOL_REVIEW.md)。模型首稿给出0张GPU与正推理GPU-hours，违反既有Pydantic规则；当时的JSON Schema却没有表达这项条件。修复将可用标准JSON Schema表达的资源约束公布给模型，避免本地校验具有未公开的额外要求。

`src/arc/schemas.py`的ResourceEstimate新增`allOf`、`if/then`：wall time使用hours，训练/推理使用GPU-hours；GPU数量大于0时须有非空型号与正显存；GPU数量为0时非空GPU-hours范围的上界不能为正。原字段、Pydantic校验器和接受语义保持不变，空GPU范围与零范围仍合法。数值区间上下界的比较仍由本地校验负责，标准JSON Schema没有跨字段数值比较操作；不能声称所有语义校验都能由schema证明。

`tests/test_resource_schema.py`新增15项测试，对完整DeveloperResult envelope执行JSON Schema与Pydantic双重校验，覆盖合法CPU/GPU配置、错误单位、缺失GPU配置，以及真实首稿的两处0 GPU/正GPU-hours错误。没有修改保存的首稿、修复稿、研究卡或科学判断，没有提高修复次数或降低验收标准。

本地相关测试53项通过。最终远端完整测试、代码提交及独立安装证据由交付包`verification/release-verification.json`和对应日志记录；实际请求验证使用原开发输入的新run `arc-vnext-validation-20260907.explicit_input_schema_v3.run`，结果另见最终验收快照。旧v2失败不能因新实现通过测试而改记为成功；新run只计入显式输入L2，不计自然同卡L3。

## 相关主张修订规则与最终工程验证

另一个开发用例暴露了同类说明缺口：`affected_claims`必须恰等于完整Claim对象的实际增删/变化集合，不能包含完全未变的主张。`prompts/roles/developer.md`追加现有规则，只适用于已有原卡的修订；原任务书完整前缀及IMPORT规则保留。`tests/test_prompts.py`检查规则进入实际渲染提示词，原有变更校验仍由`tests/test_claim_targets.py`验证。真实旧失败详见[定向补证及修订审计](REAL_TARGETED_RETRIEVAL_REVIEW.md)。

提交`a14da30f31a1541b9a5732c6aa3b85ab9dc689f9`完整测试 **342 passed / 65.59s**，日志`work/tests-final-contract.log`。从该提交git archive构建wheel和sdist，在独立`.venv-wheel`安装后于`/tmp`验证CLI、包资源及源码一致性。schema SHA256为`4476d42a2aa1f6aad93f673a8e2af6648bd96b01445512c202ce327da4cb0587`，developer Markdown为`a32e273836f489721465ba3a1226a83f0231c253c9968d58312c42dbfe71efef`；安装件与源码分别相等。

之前`97d4766`已通过341项测试，但第一次辅助打包错误地使用`--no-isolation`，环境没有setuptools导致构建失败。保留`work/wheel-build-97d4766.log`，随后恢复标准隔离构建和uv独立安装。它是打包辅助脚本错误，不能将其写成第一次构建成功，也不涉及新模型费用。后续完整验证结果以上述a14da30为准。
