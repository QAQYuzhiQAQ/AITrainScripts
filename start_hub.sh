#!/usr/bin/env bash
# macOS / Linux 一键启动 Hub
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 start_hub.py
elif command -v python >/dev/null 2>&1; then
  exec python start_hub.py
else
  echo "错误: 未找到 python3 或 python，请先安装 Python 3.9+"
  exit 1
fi
