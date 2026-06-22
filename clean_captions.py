#!/usr/bin/env python3
"""
Caption 规则清洗（命令行）

按 configs/caption/*.toml 预设批量清洗 .txt caption。

示例:
  python clean_captions.py --dir "C:/Document/参考图/LoRATrain/LOL/Akali/new"
  python clean_captions.py --dir ./dataset --preset akali --dry-run
"""

from __future__ import annotations

import argparse

from img_tools.caption import CaptionCleanOptions, clean_captions_in_dir, list_presets
from img_tools.common import print_job_result


def main() -> int:
    presets = list_presets()
    preset_help = ", ".join(p["id"] for p in presets) if presets else "default"

    parser = argparse.ArgumentParser(description="Caption 规则清洗")
    parser.add_argument("--dir", required=True, help="含 .txt 的目录")
    parser.add_argument("--preset", default="default", help=f"预设 ID（{preset_help}）")
    parser.add_argument("--recursive", action="store_true", help="递归子目录")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写回文件")
    parser.add_argument("--trigger", default=None, help="覆盖预设触发词")
    parser.add_argument("--strip", default=None, help="额外删除 tag，逗号分隔")
    parser.add_argument("--ensure", default=None, help="额外补充 tag，逗号分隔")
    args = parser.parse_args()

    opts = CaptionCleanOptions(
        preset=args.preset,
        recursive=args.recursive,
        dry_run=args.dry_run,
        trigger_word=args.trigger,
        strip_tags=args.strip,
        ensure_tags=args.ensure,
    )

    result = clean_captions_in_dir(args.dir, opts)
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
