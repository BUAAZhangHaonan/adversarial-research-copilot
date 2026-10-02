# ARC 卡牌研究所

用卡牌浏览研究想法，并把选中的想法展开成方案。召唤对应 `discover`，试炼对应 `develop`，审判对应 `run`。收藏页保存各轮研究记录，先展示当前结果，再按需打开卡片、技术分析、文献和原始文档。

## 代码与数据

`client/` 是 React、TypeScript 和 Vite 前端。`server/` 是 FastAPI 服务，负责登录、任务管理、研究记录读取和静态文件托管。`scripts/start.sh` 用于准备服务环境、构建前端并启动服务。

网页通过 ARC 命令行提交任务，并读取 ARC 的 SQLite 状态与输出文件。任务关联使用子进程输出中的 run ID；相同研究主题不会被用来猜测任务归属。费用未完整记录时，界面保留未知状态。取消任务前会核对子进程身份，取消操作不会伪造 ARC 的暂停或完成状态。

本目录是 ARC 仓库的 `web/`，默认直接使用仓库根目录的 ARC 核心。`server/config.yaml` 中的 `backend_root: ../..` 相对于该配置文件解析。需要使用其他核心工作区时，可调整该相对路径。服务数据默认保存在 `server/data/`，其中账号、研究记录和日志均不进入版本控制。

此公开源码不包含真实研究数据库、历史报告、账号、密钥或历史截图。测试示例均为合成数据。依赖历史研究夹具的本地测试保留在原工作区，没有纳入公开源码。

## 启动

在 ARC 核心仓库运行 `uv sync --locked --extra dev`，并按核心仓库的 `.env.example` 配置本地环境。环境文件应保留在本地。

在本目录运行：

```bash
bash scripts/start.sh
```

默认地址为 `http://localhost:8210`，登录后才能读取研究记录。初次账号由管理员通过命令行建立：

```bash
cd server
.venv/bin/python manage.py adduser <name> [--admin]
```

该命令会交互式读取密码。其他账号管理命令见 `manage.py --help`。修改部署地址、认证方式或研究后端前，应单独核对部署配置。

## 阅读与卡牌

主卡展示场景、研究问题、核心想法、最近工作与研究价值。技术分析、反面结果、证据限制和来源保留在可展开的独立区域。没有写作展示文本的历史记录会显示原始内容，并说明它来自早期记录。

现有百分比、假设、判断与文献引用保留原文。展示上的分区不生成新的科研结论，也不修改研究记录。未完成任务继续使用进度与恢复页面，已完成任务进入阅读页面。读取受保护版本时遵守服务端权限；旧服务缺少版本接口而返回 404 时，使用原有受保护的读取接口。

配色使用深靛色桌面、奶油色卡面和金色品牌元素。召唤用紫蓝、试炼用蓝银、审判用暖金。翻牌、页面入场、弹窗和展开内容使用短时动效；系统设置为减少动效时，装饰动画关闭，操作仍可用。

## 验证

服务测试使用临时目录、合成 SQLite 数据和模拟命令行，不调用模型：

```bash
cd server
.venv/bin/python -m pytest tests -q
```

前端类型、构建与内容保护检查：

```bash
cd client
npm ci
./node_modules/.bin/tsc --noEmit --incremental false
node scripts/reading-content.mjs
npm run build
```

浏览器检查需要可用的 Chromium 或 Chrome。启动静态页面后运行：

```bash
BASE_URL=http://localhost:8210 node scripts/regression-client.mjs
BASE_URL=http://localhost:8210 node scripts/reading-regression.mjs
# 完整合成浏览器验收：直接托管已构建的 dist，并同时运行原有交互回归
RUN_EXISTING_REGRESSIONS=1 node scripts/card-experience-regression.mjs
```

这些浏览器脚本拦截 API，使用合成记录，检查错误状态、暂停恢复、翻牌、卡片、原始文档和移动端阅读。运行结果与截图属于本地生成文件，不进入 Git。

## 静态页面更新

服务从 `client/dist/` 读取前端。仅更新界面时，先备份完整的当前目录和入口文件，再添加带哈希的资源，最后原子替换 `index.html`。保留旧资源，以便仍打开旧页面的浏览器继续访问。回滚时恢复此前入口文件。

上线后核对主页和所引用资源的哈希，并确认未登录访问 `/api/auth/me`、`/api/runs` 和 `/api/health` 仍返回 401。静态页面更新无需重启服务、修改账号或变更研究后端。
