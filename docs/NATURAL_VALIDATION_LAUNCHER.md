# 自然流程启动与恢复

`scripts/start_natural_validation.py` 组合现有 `new_run`、`execute` 和检查点恢复；调用时才会创建阶段并使用模型。导入脚本或查看 `--help` 不写数据库、不调用模型。

材料准备 run `functional-20260908-early-stopping-material` 只提供原题、用户条件和已登记证据。新 discover 有独立 campaign 和 draw 计数，最多 5 次，Agent 可以提前 STOP。阶段使用现有父账本 `arc-vnext-validation-20260907`，各子阶段 200 CNY；沿用 Flash/Pro 和 max，父账本仍限制累计费用。父账本有未结算调用时不启动另一个阶段。

在仓库根目录执行（以下命令会启动真实付费阶段）：

```bash
.venv/bin/python scripts/start_natural_validation.py \
  --data-dir /home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation \
  --prefix functional-20260908-natural discover --draws 5
```

discover 完成后先读对应 `reports/<run-id>/`。由开发主线程审阅候选的价值和致命风险，选择确切 card/version，再单独运行：

```bash
.venv/bin/python scripts/start_natural_validation.py \
  --data-dir /home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation \
  --prefix functional-20260908-natural develop \
  --card CARD_ID --version VERSION --selection-reason '填写该版本值得继续检查的具体理由'
```

develop 完成后再次审阅，使用同样参数形式将子命令改成 `run`，传入 develop 的最新已审核 card/version。脚本不自动选卡或跨阶段；拒绝卡必须先解决拒绝原因或改选其他候选，未审核版本不能继续。开发选择理由写入该阶段记录；正式服务没有 CodeX 评审环路。

恢复既有阶段保留原 run、配置、账本、成功任务和 draw 计数：

```bash
.venv/bin/python scripts/start_natural_validation.py \
  --data-dir /home/g203/zhanghaonan/arc-vnext-20260907/.arc-validation \
  --prefix functional-20260908-natural resume --stage discover
```

`--stage` 也支持 `develop`、`run`。协议纠错额度耗尽时，按原有 `arc retry-task --task-key ... --reason ...` 显式创建任务重试；本脚本不静默重置纠错额度。所有命令应顺序执行。报告中的材料准备完成、工作流完成和科学推荐是不同状态。
