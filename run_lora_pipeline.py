#!/usr/bin/env python3
"""
LoRA 角色训练完整流水线（命令行）

用户需先创建 characterABC/ 并将原始图片放在根目录。

示例:
  python run_lora_pipeline.py --root "C:/LoRA/characterABC" --preset akali --lora-preset morgana_star_nemesis
"""

from __future__ import annotations

import argparse

from img_tools.common import print_job_result
from img_tools.lora_pipeline import LoraPipelineOptions, run_lora_pipeline
from img_tools.workflow import ResizeMode


def main() -> int:
    parser = argparse.ArgumentParser(description="LoRA 角色训练完整流水线（8 步）")
    parser.add_argument("--root", required=True, help="角色根目录 characterABC")
    parser.add_argument("--repeat", type=int, default=10, help="重复次数，生成 output/{n}_output/")
    parser.add_argument("--mode", choices=["area_64", "fixed_canvas"], default="area_64")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--prefix", default="", help="重命名前缀")
    parser.add_argument("--digits", type=int, default=4)
    parser.add_argument("--caption-preset", default="default")
    parser.add_argument("--trigger", default="")
    parser.add_argument("--lora-preset", default="morgana_star_nemesis")
    parser.add_argument("--train-data-dir", default="", help="忽略；固定使用 output/")
    parser.add_argument("--output-name", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--epochs", type=int, default=0)
    args = parser.parse_args()

    overrides: dict = {}
    if args.output_name:
        overrides["output_name"] = args.output_name
    if args.output_dir:
        overrides["output_dir"] = args.output_dir
    if args.epochs > 0:
        overrides["max_train_epochs"] = args.epochs

    opts = LoraPipelineOptions(
        character_root=args.root,
        repeat_count=args.repeat,
        resize_mode=ResizeMode(args.mode),
        target_width=args.width,
        target_height=args.height,
        rename_prefix=args.prefix,
        rename_digits=args.digits,
        caption_preset=args.caption_preset,
        trigger_word=args.trigger,
        lora_preset=args.lora_preset,
        lora_overrides=overrides,
    )

    def on_progress(prog: dict, line: str) -> None:
        step = prog.get("step", "?")
        total = prog.get("total_steps", 8)
        msg = prog.get("message", line)
        print(f"[{step}/{total}] {msg}")

    result = run_lora_pipeline(opts, progress_callback=on_progress)
    print_job_result(result)
    if result.ok:
        print("\n>>> 训练已完成！ <<<")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
