# 同一问题的运行版本

版本关系和展示选择保存在 `server/data/run_versions.json`，与 ARC 的
`arc.sqlite`、报告、模型输出和费用账本分开。没有版本记录时，现有展示保持原样。
读取接口不会创建版本记录；不会根据主题文字、创建时间或科研判断推断同题关系。

每个问题由明确提供的 `problem_id` 标识，每次 discover 是一个版本的起点。
新的 discover 必须指明同题的前一版本。develop 和 run 可以登记为该版本的后续阶段，
通过 `parent_run_id` 明确连接。这样切换版本时，旧 discover 及其已登记后续阶段一起退出默认展示。
不同问题即使题目文字相同，也不会相互覆盖。尚未登记的历史运行继续展示，须逐个明确归属。

## 登记和选择

以下接口需要管理员登录，只改变展示元数据：

| 接口 | 请求内容 |
|---|---|
| `GET /api/run-versions` | 查看关系、当前选择、修订号和操作记录 |
| `POST /api/run-versions/current` | `{ "problem_id": "question-a", "run_id": "old-discover" }`，登记目前展示的起点 |
| `POST /api/run-versions/versions` | `{ "problem_id": "question-a", "run_id": "new-discover", "previous_run_id": "old-discover" }` |
| `POST /api/run-versions/stages` | `{ "run_id": "old-develop", "parent_run_id": "old-discover" }`；run 可再连接 develop |
| `POST /api/run-versions/selection` | `{ "problem_id": "question-a", "run_id": "new-discover", "expected_selected": "old-discover", "reviewed": true }` |

登记新版本不会自动选择它。失败、暂停、运行中的新版本不会替换原结果。
选择接口要求 discover 已完成、有灵感卡、报告和主卡已写入，并要求管理员明确确认审核。
这些结构条件不能证明科研质量；主卡与技术分析的内容仍须审核，未做科研实验本身不阻止选择。
`expected_selected` 用于避免并发操作覆盖另一位操作者刚做出的选择。

对现有多份旧运行的归属，应在新结果成功并审核后明确登记，再切换选择。
不能预先隐藏现有结果以等待新输出。不要通过批量主题匹配生成版本关系。

## 默认展示与后台保留

运行列表、运行详情、文件读取、首页任务列表和任务详情遵守同一选择。
已登记且未选中的版本不会出现在默认列表；其详情和文件接口返回 410。
`GET /api/runs/{run_id}/visibility` 返回是否可展示及当前选定起点。
打开的详情页和带任务编号的召唤、试炼、审判页每五秒检查一次；
切换后卸载旧卡片和弹窗，转到选定版本。任务是否仍可展示由
`GET /api/jobs/{job_id}/visibility` 提供；尚未关联运行的任务继续正常显示进度。
卡片数量来自同一可展示详情，不累计旧版本。

管理员可以通过 `GET /api/run-versions/runs/{run_id}` 和其 `/file?name=…`
接口查看留在后台的完整旧结果。普通页面不提供历史版本入口。
ARC 的原始运行状态、科研字段、报告文件和账本不因展示选择变化。

每次元数据修改先保存完整旧版本到 `run_versions.json.backups/`，
再在同一目录原子替换新记录。进程间锁避免并发丢失登记。
需要恢复展示时，可明确选择先前已完成的版本，操作记录和所有版本关系继续保留。
本功能不需要修改现有数据库结构，也不会在启动时迁移、登记或切换真实运行。

## 验证与部署

```bash
cd server
.venv/bin/python -m pytest tests/test_run_versions.py -q
```

测试只使用临时目录、合成运行和本地内存 API，不调用模型、不连接网络。
前端构建和浏览器回归应输出到隔离目录，避免覆盖正在托管的 `client/dist`。
代码提交、生产部署、真实版本登记和选择是分别执行的操作。
