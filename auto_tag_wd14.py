#!/usr/bin/env python3
"""
WD14 自动打标（命令行）

为图片目录批量生成 Kohya / LoRA 训练用的同名 .txt caption。
支持 Caption 预设（打标排除 + 打标后规则清洗）。

示例:
  python auto_tag_wd14.py --dir "C:/Document/参考图/LoRATrain/LOL/Akali/new"
  python auto_tag_wd14.py --dir ./dataset --preset akali --trigger "Akali test"
  python auto_tag_wd14.py --dir ./dataset --preset akali --no-clean
"""

from __future__ import annotations

import argparse

from img_tools.caption import CaptionCleanOptions, clean_captions_in_dir, get_tag_undesired_for_preset, get_trigger_for_preset
from img_tools.common import JobResult, print_job_result
from img_tools.tagger import WD14TagOptions, tag_images_wd14


def _merge_results(tag: JobResult, clean: JobResult) -> JobResult:
    return JobResult(
        ok=tag.ok and clean.ok,
        message=f"{tag.message} → {clean.message}",
        processed=tag.processed + clean.processed,
        skipped=tag.skipped + clean.skipped,
        errors=[*tag.errors, *clean.errors],
        details=[*tag.details, *clean.details],
        outputs=[*tag.outputs, *clean.outputs],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="WD14 自动打标 → 同名 .txt")
    parser.add_argument("--dir", required=True, help="图片目录")
    parser.add_argument(
        "--model",
        default="SmilingWolf/wd-vit-tagger-v3",
        help="HuggingFace 模型 repo_id",
    )
    parser.add_argument("--model-dir", default="wd14_tagger_model", help="模型缓存目录")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--general-threshold", type=float, default=0.35)
    parser.add_argument("--character-threshold", type=float, default=0.1)
    parser.add_argument("--preset", default="default", help="Caption 预设（打标排除 + 清洗规则）")
    parser.add_argument("--trigger", default="", help="触发词（覆盖预设）")
    parser.add_argument("--undesired", default="", help="额外排除 tag，逗号分隔")
    parser.add_argument("--recursive", action="store_true", help="递归子目录")
    parser.add_argument("--remove-underscore", action="store_true", help="下划线转空格")
    parser.add_argument("--append", action="store_true", help="追加到已有 caption，不覆盖")
    parser.add_argument("--force-download", action="store_true", help="重新下载模型")
    parser.add_argument("--no-clean", action="store_true", help="打标后不执行规则清洗")
    args = parser.parse_args()

    preset_undesired = get_tag_undesired_for_preset(args.preset)
    preset_trigger = get_trigger_for_preset(args.preset)

    undesired = args.undesired.strip()
    if not undesired:
        undesired = preset_undesired
    elif preset_undesired:
        merged = {t.strip() for t in (undesired + ", " + preset_undesired).split(",") if t.strip()}
        undesired = ", ".join(sorted(merged))

    trigger = args.trigger.strip() or preset_trigger

    opts = WD14TagOptions(
        repo_id=args.model,
        model_dir=args.model_dir,
        batch_size=args.batch_size,
        general_threshold=args.general_threshold,
        character_threshold=args.character_threshold,
        recursive=args.recursive,
        remove_underscore=args.remove_underscore,
        undesired_tags=undesired,
        always_first_tags=trigger,
        append_tags=args.append,
        force_download=args.force_download,
    )

    tag_result = tag_images_wd14(args.dir, opts)
    if args.no_clean or not tag_result.ok:
        print_job_result(tag_result)
        return 0 if tag_result.ok else 1

    clean_opts = CaptionCleanOptions(
        preset=args.preset,
        recursive=args.recursive,
        dry_run=False,
        trigger_word=trigger or None,
    )
    clean_result = clean_captions_in_dir(args.dir, clean_opts)
    result = _merge_results(tag_result, clean_result)
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
