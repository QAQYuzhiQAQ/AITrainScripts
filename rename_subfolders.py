#!/usr/bin/env python3
"""
子文件夹批量重命名（命令行）

为指定目录下的子文件夹去掉空格并加 10_ 前缀（Kohya 训练目录常用）。

示例:
  python rename_subfolders.py --dir "C:/LoRA/characterABC/output"
  python rename_subfolders.py --dir ./output --prefix "10_" --apply --recursive
"""

from __future__ import annotations

import argparse

from img_tools.common import print_job_result
from img_tools.rename_folders import SubfolderRenameOptions, rename_subfolders


def main() -> int:
    parser = argparse.ArgumentParser(description="子文件夹重命名：去空格 + 加前缀")
    parser.add_argument("--dir", required=True, help="目标根目录")
    parser.add_argument("--prefix", default="10_", help="文件夹名前缀（默认 10_）")
    parser.add_argument("--no-remove-spaces", action="store_true", help="不去掉空格")
    parser.add_argument("--recursive", action="store_true", help="包含所有层级的子文件夹")
    parser.add_argument("--apply", action="store_true", help="实际执行（默认仅预览）")
    args = parser.parse_args()

    opts = SubfolderRenameOptions(
        prefix=args.prefix,
        remove_spaces=not args.no_remove_spaces,
        recursive=args.recursive,
        dry_run=not args.apply,
    )
    result = rename_subfolders(args.dir, options=opts)
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
