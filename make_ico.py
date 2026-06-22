#!/usr/bin/env python3
"""
图片批量转 ICO（命令行）

示例:
  python make_ico.py --dir "C:/icons/source"
  python make_ico.py --dir ./images --output ./icons --sizes "16,32,256" --recursive
"""

from __future__ import annotations

import argparse

from img_tools.common import print_job_result
from img_tools.to_ico import ToIcoOptions, convert_images_to_ico, parse_ico_sizes


def main() -> int:
    parser = argparse.ArgumentParser(description="PNG/JPG 等 → Windows ICO")
    parser.add_argument("--dir", required=True, help="图片来源目录")
    parser.add_argument("--output", default="", help="输出目录（留空则与原图同目录）")
    parser.add_argument(
        "--sizes",
        default="16,32,48,64,128,256",
        help="ICO 内嵌尺寸，逗号分隔",
    )
    parser.add_argument("--max-canvas", type=int, default=256, help="主图画布边长（像素）")
    parser.add_argument("--recursive", action="store_true", help="递归子目录")
    args = parser.parse_args()

    opts = ToIcoOptions(
        sizes=parse_ico_sizes(args.sizes),
        max_canvas=max(16, args.max_canvas),
        recursive=args.recursive,
    )
    result = convert_images_to_ico(
        args.dir,
        args.output or None,
        options=opts,
    )
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
