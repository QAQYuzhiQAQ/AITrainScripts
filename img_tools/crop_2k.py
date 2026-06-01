"""2K PNG 固定区域裁剪。"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from img_tools.common import JobResult, ensure_dir

TARGET_SIZE = (2560, 1440)
CROP_BOX = (320, 0, 2240, 1440)


def crop_2k_png_recursive(
    input_root: str | Path,
    output_root: str | Path,
    *,
    target_size: tuple[int, int] = TARGET_SIZE,
    crop_box: tuple[int, int, int, int] = CROP_BOX,
) -> JobResult:
    """递归扫描，仅处理尺寸为 target_size 的 PNG，裁剪后保持目录结构输出。"""
    input_root = Path(input_root)
    output_root = Path(output_root)

    if not input_root.is_dir():
        return JobResult(ok=False, message=f"输入目录无效: {input_root}")

    processed = 0
    skipped = 0
    errors: list[str] = []
    details: list[str] = []
    outputs: list[Path] = []

    for root, _, files in os.walk(input_root):
        for filename in files:
            if not filename.lower().endswith(".png"):
                continue

            img_path = Path(root) / filename
            relative_path = os.path.relpath(root, input_root)
            target_sub_dir = output_root / relative_path

            try:
                with Image.open(img_path) as img:
                    if img.size == target_size:
                        ensure_dir(target_sub_dir)
                        save_path = target_sub_dir / filename
                        img.crop(crop_box).save(save_path)
                        processed += 1
                        outputs.append(save_path)
                        rel_display = os.path.join(relative_path, filename)
                        details.append(f"处理: {rel_display}")
                    else:
                        skipped += 1
                        rel_display = os.path.join(relative_path, filename)
                        details.append(f"跳过: {rel_display} (尺寸 {img.size})")
            except Exception as e:
                errors.append(f"{filename}: {e}")

    if processed == 0 and not errors:
        return JobResult(
            ok=False,
            message="没有符合尺寸的 PNG 被处理",
            skipped=skipped,
            errors=errors,
            details=details,
        )

    return JobResult(
        ok=True,
        message=f"裁剪完成：处理 {processed} 张，跳过 {skipped} 张",
        processed=processed,
        skipped=skipped,
        errors=errors,
        details=details,
        outputs=outputs,
    )
