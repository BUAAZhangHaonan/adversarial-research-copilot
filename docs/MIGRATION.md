# 迁移说明

新版保留 `discover`、`develop`、`run` 三个入口，默认各阶段结束即停。
`pipeline`、`chat-mode`、多模型旧注册表、YAML/关键词控制、评分收敛、reviewer/drift-monitor 嵌套循环已移除。
不提供旧状态迁移或兼容调用。旧 reports、用户研究材料、密钥与 references 均保留原处。

新调查使用独立数据目录，SQLite 为状态和预算权威记录。
旧提案如需继续，可显式 `run --proposal old-proposal.md` 或导入符合新 schema 的卡片；
这会创建新调查，不继承旧分数、通过状态或旧预算。

使用现有 `DEEPSEEK_API_KEY/BASE_URL` 和实际 MCP 环境配置。
旧 GPT/GLM、温度、fallback、pipeline角色和输出压缩环境变量不再控制新版。
第一版统一 Flash/Pro、显式 max，生产提示词只在 `prompts/` 中维护。

运行日志、原始模型消息、文献和数据库默认私有且被 gitignore 排除；不要发布到 GitHub。
按2026-09-07用户要求，全部实现保留原细粒度提交快进到master，后续仅维护master，不再新建分支。原验证目录作为detached HEAD档案保留；当前状态见[MASTER_STATUS.md](MASTER_STATUS.md)。
