#!/usr/bin/env python3
"""
LoRA 数据准备一键工作流（命令行）

示例:
  python prepare_dataset.py \\
    --source /path/to/raw \\
    --output /path/to/out \\
    --width 1024 --height 1024 \\
    --mode area_64 \\
    --prefix "" --digits 4
"""

from __future__ import annotations

import argparse
from pathlib import Path

from img_tools.workflow import RenameMode, ResizeMode, WorkflowRenameOptions, run_prepare_workflow
from img_tools.common import print_job_result


def main() -> int:
    parser = argparse.ArgumentParser(description="LoRA 图片准备一键工作流")
    parser.add_argument("--source", required=True, help="未处理图片目录")
    parser.add_argument("--output", required=True, help="处理后输出目录")
    parser.add_argument("--width", type=int, default=1024, help="目标宽（像素）")
    parser.add_argument("--height", type=int, default=1024, help="目标高（像素）")
    parser.add_argument(
        "--mode",
        choices=["area_64", "fixed_canvas"],
        default="area_64",
        help="area_64=等效面积+64倍数画布; fixed_canvas=固定宽高透明填充",
    )
    parser.add_argument("--recursive", action="store_true", help="递归处理子文件夹")
    parser.add_argument(
        "--rename-mode",
        choices=["numbered", "sequential", "none"],
        default="numbered",
    )
    parser.add_argument("--prefix", default="", help="重命名前缀（numbered 模式）")
    parser.add_argument("--start-num", type=int, default=1)
    parser.add_argument("--digits", type=int, default=4)
    parser.add_argument("--start-index", type=int, default=1, help="sequential 模式起始序号")
    parser.add_argument(
        "--no-sync-captions",
        action="store_true",
        help="不重命名配对的 .txt / .caption",
    )
    args = parser.parse_args()

    rename = WorkflowRenameOptions(
        mode=RenameMode(args.rename_mode),
        prefix=args.prefix,
        start_num=args.start_num,
        digits=args.digits,
        start_index=args.start_index,
        sync_captions=not args.no_sync_captions,
    )

    result = run_prepare_workflow(
        args.source,
        args.output,
        args.width,
        args.height,
        ResizeMode(args.mode),
        recursive=args.recursive,
        rename=rename,
    )
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
