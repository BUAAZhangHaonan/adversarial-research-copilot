# Case Studies（典型实验分析案例）

> 注意：这三个目录是 2026-09-05/06 审阅修复批次的端到端验证运行，作为典型分析案例
> 暂存入库，**后续将撤回**（见 docs/plans/2026-09-06-e2e-experiments.md 的完整记录）。
> artifacts 命名为改版前的 chat-mode 风格（CHAT_TRANSCRIPT.md 等），改版后为
> DEVELOP_TRANSCRIPT.md。

| 目录 | 模式 | 看点 |
|---|---|---|
| `20260906_014858_deepseek_v4_flash_deepseek_v4_pro` | discover（60/12/8 全参数） | 7 KEEP + 1 PIVOT、查重材料进品味门、有条件否决记录、COST_REPORT（含 MCP 调用计数）、单篇深读失败优雅跳过 |
| `20260906_014859_..._deepseek_v4_pro_deepseek_v4_pro` | develop（原 chat-mode） | 3 轮即路由 next_action=EXPERIMENT（对比修复前同主题 166 轮）；争点表 1→2；PENDING_ACTIONS.md；三 structured_ok=True |
| `20260906_014859_..._01` | debate | 6 轮全部合法 YAML 解析（protocol_errors=0），无正文误判停止，诚实 CONTINUE 到轮数上限 |
