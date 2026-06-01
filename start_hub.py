#!/usr/bin/env python3
"""
AITrainScripts Hub 一键启动（Windows / macOS / Linux 通用）

用法:
  python start_hub.py
  或双击 start_hub.bat（Windows）、start_hub.command（macOS）
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"
HUB_URL = "http://127.0.0.1:8765"


def pause_if_interactive() -> None:
    """双击启动时保持窗口，便于查看报错。"""
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            input("\n按 Enter 键退出… ")
        except (EOFError, KeyboardInterrupt):
            pass


def run(cmd: list[str], **kwargs) -> None:
    print(f"\n>> {' '.join(cmd)}\n")
    subprocess.check_call(cmd, cwd=ROOT, **kwargs)


def main() -> int:
    os.chdir(ROOT)
    py = sys.executable

    print("=" * 50)
    print("  AITrainScripts Hub 一键启动")
    print("=" * 50)
    print(f"  目录: {ROOT}")
    print(f"  Python: {py}")
    print()

    if not REQUIREMENTS.is_file():
        print(f"错误: 未找到 {REQUIREMENTS}", file=sys.stderr)
        pause_if_interactive()
        return 1

    try:
        print("正在检查 / 安装依赖…")
        run([py, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    except subprocess.CalledProcessError:
        print("\n依赖安装失败。请确认已安装 Python 3.9+ 且 pip 可用。", file=sys.stderr)
        pause_if_interactive()
        return 1

    print()
    print("=" * 50)
    print(f"  请在浏览器打开: {HUB_URL}")
    print("  关闭本窗口即停止服务（Ctrl+C）")
    print("=" * 50)
    print()

    try:
        run([py, "-m", "hub"])
    except KeyboardInterrupt:
        print("\n已停止 Hub。")
    except subprocess.CalledProcessError:
        print("\nHub 启动失败，请查看上方报错。", file=sys.stderr)
        pause_if_interactive()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
