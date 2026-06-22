#!/usr/bin/env python3
"""
图片格式互转（命令行，保持原始尺寸）

示例:
  python convert_format.py --dir "C:/photos" --format webp
  python convert_format.py --dir ./img --format jpeg --no-in-place --output ./out
"""

from __future__ import annotations

import argparse

from img_tools.common import print_job_result
from img_tools.format_convert import FormatConvertOptions, convert_images_format, normalize_target_format


def main() -> int:
    formats = "png, jpeg, webp, bmp, gif, tiff"
    parser = argparse.ArgumentParser(description=f"文件夹内图片格式互转（{formats}）")
    parser.add_argument("--dir", required=True, help="目标文件夹")
    parser.add_argument("--output", default="", help="输出目录（非原地模式时可选）")
    parser.add_argument("--format", required=True, help=f"目标格式：{formats}")
    parser.add_argument("--quality", type=int, default=90, help="JPEG/WebP 质量 1–100")
    parser.add_argument("--no-in-place", action="store_true", help="不原地转换")
    parser.add_argument("--no-recursive", action="store_true", help="不处理子文件夹")
    parser.add_argument(
        "--include-same",
        action="store_true",
        help="不跳过已是目标格式的文件（仍会重新编码）",
    )
    args = parser.parse_args()

    try:
        key, _, _ = normalize_target_format(args.format)
    except ValueError as e:
        print(e)
        return 1

    opts = FormatConvertOptions(
        target_format=key,  # type: ignore[arg-type]
        quality=max(1, min(100, args.quality)),
        recursive=not args.no_recursive,
        in_place=not args.no_in_place,
        skip_same_format=not args.include_same,
    )
    result = convert_images_format(args.dir, args.output or None, options=opts)
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
