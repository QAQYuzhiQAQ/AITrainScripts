#!/usr/bin/env python3
"""
LoRA 训练启动器（调用 lora-scripts / Kohya）

示例:
  python train_lora.py
  python train_lora.py --preset morgana_star_nemesis
  python train_lora.py --train-data-dir "C:/path/to/dataset" --output-name MyLora_v1
"""

from __future__ import annotations

import argparse

from img_tools.common import print_job_result
from img_tools.lora_train import list_presets, run_lora_train


def main() -> int:
    presets = list_presets()
    default_preset = presets[0]["id"] if presets else "morgana_star_nemesis"

    parser = argparse.ArgumentParser(description="启动 lora-scripts LoRA 训练")
    parser.add_argument("--preset", default=default_preset, help="configs/lora/ 下的预设名")
    parser.add_argument("--train-data-dir", default="", help="覆盖 train_data_dir")
    parser.add_argument("--output-name", default="", help="覆盖 output_name")
    parser.add_argument("--output-dir", default="", help="覆盖 output_dir")
    parser.add_argument("--max-train-epochs", type=int, default=0, help="覆盖 max_train_epochs")
    parser.add_argument("--list-presets", action="store_true", help="列出可用预设")
    args = parser.parse_args()

    if args.list_presets:
        if not presets:
            print("未找到预设，请在 configs/lora/ 添加 .toml 文件。")
            return 1
        for p in presets:
            print(f"  {p['id']}")
        return 0

    overrides: dict = {}
    if args.train_data_dir:
        overrides["train_data_dir"] = args.train_data_dir
    if args.output_name:
        overrides["output_name"] = args.output_name
    if args.output_dir:
        overrides["output_dir"] = args.output_dir
    if args.max_train_epochs > 0:
        overrides["max_train_epochs"] = args.max_train_epochs

    result = run_lora_train(args.preset, overrides=overrides or None)
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
