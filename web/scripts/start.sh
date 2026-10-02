#!/usr/bin/env bash
# arc-arena 一键启动：构建前端 + 启动 BFF（0.0.0.0:8210，面向内网）
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.local/bin:$PATH"

# 1. server venv
if [ ! -x server/.venv/bin/python ]; then
  echo "[1/3] 初始化 server venv..."
  python3 -m venv server/.venv
  server/.venv/bin/pip install -q -r server/requirements.txt
fi

# 2. ARC v2（adversarial-research-copilot master 工作区）就绪检查
ARC_ROOT="${ARC_ROOT:-..}"
if [ ! -x "$ARC_ROOT/.venv/bin/arc" ]; then
  echo "[2/3] ARC v2 未就绪：$ARC_ROOT/.venv/bin/arc 不存在"
  echo "      ARC v2 仓库（adversarial-research-copilot）需与 arc-arena 目录同级存放，"
  echo "      并执行: cd adversarial-research-copilot && uv sync --locked --extra dev"
  echo "      （或修改 server/config.yaml 的 backend_root 指向实际位置）"
  exit 1
fi

# 3. 前端构建（源码有更新时）
echo "[3/3] 构建前端..."
(cd client && npm ci && npm run build)

# 4. 启动
echo "启动 arc-arena: http://0.0.0.0:8210"
cd server
exec .venv/bin/python run.py
