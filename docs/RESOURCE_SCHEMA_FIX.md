# 资源估计 schema 可见性修复

本修复来自开发输入的真实失败，原件和错误分层见[L2导入审计](L2_SCHEMA_FORK_PROTOCOL_REVIEW.md)。模型首稿给出0张GPU与正推理GPU-hours，违反既有Pydantic规则；当时的JSON Schema却没有表达这项条件。修复将可用标准JSON Schema表达的资源约束公布给模型，避免本地校验具有未公开的额外要求。

`src/arc/schemas.py`的ResourceEstimate新增`allOf`、`if/then`：wall time使用hours，训练/推理使用GPU-hours；GPU数量大于0时须有非空型号与正显存；GPU数量为0时非空GPU-hours范围的上界不能为正。原字段、Pydantic校验器和接受语义保持不变，空GPU范围与零范围仍合法。数值区间上下界的比较仍由本地校验负责，标准JSON Schema没有跨字段数值比较操作；不能声称所有语义校验都能由schema证明。

`tests/test_resource_schema.py`新增15项测试，对完整DeveloperResult envelope执行JSON Schema与Pydantic双重校验，覆盖合法CPU/GPU配置、错误单位、缺失GPU配置，以及真实首稿的两处0 GPU/正GPU-hours错误。没有修改保存的首稿、修复稿、研究卡或科学判断，没有提高修复次数或降低验收标准。

本地相关测试53项通过。最终远端完整测试、代码提交及独立安装证据由交付包`verification/release-verification.json`和对应日志记录；实际请求验证使用原开发输入的新run `arc-vnext-validation-20260907.explicit_input_schema_v3.run`，结果另见最终验收快照。旧v2失败不能因新实现通过测试而改记为成功；新run只计入显式输入L2，不计自然同卡L3。
