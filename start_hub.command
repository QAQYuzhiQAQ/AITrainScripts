#!/bin/bash
# macOS 双击启动（Finder 中双击此文件）
cd "$(dirname "$0")"
chmod +x start_hub.sh start_hub.command 2>/dev/null || true
exec ./start_hub.sh
