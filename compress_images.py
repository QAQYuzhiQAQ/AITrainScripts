#!/usr/bin/env python3
"""
图片按目标大小压缩（命令行）

示例:
  python compress_images.py --dir "C:/photos" --max-size 500
  python compress_images.py --dir ./img --max-size 2 --unit mb --no-in-place --output ./out
"""

from __future__ import annotations

import argparse

from img_tools.common import print_job_result
from img_tools.compress import CompressOptions, compress_images, parse_max_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="将文件夹内图片压缩到指定大小以内")
    parser.add_argument("--dir", required=True, help="目标文件夹")
    parser.add_argument("--output", default="", help="输出目录（非原地模式时可选）")
    parser.add_argument("--max-size", type=float, required=True, help="目标大小上限")
    parser.add_argument("--unit", choices=["kb", "mb", "b"], default="kb", help="大小单位")
    parser.add_argument(
        "--format",
        choices=["auto", "jpeg", "webp", "png"],
        default="auto",
        help="输出格式（auto：有透明通道用 webp，否则 jpeg）",
    )
    parser.add_argument("--no-in-place", action="store_true", help="不原地压缩，输出到其他目录")
    parser.add_argument("--no-recursive", action="store_true", help="不处理子文件夹")
    args = parser.parse_args()

    opts = CompressOptions(
        max_bytes=parse_max_bytes(args.max_size, args.unit),
        output_format=args.format,
        recursive=not args.no_recursive,
        in_place=not args.no_in_place,
    )
    result = compress_images(args.dir, args.output or None, options=opts)
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
