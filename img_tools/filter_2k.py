"""按 2K 尺寸过滤图片（支持预览 dry_run）。"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from img_tools.common import COMMON_IMAGE_EXTENSIONS, JobResult

TARGET_WIDTH = 2560
TARGET_HEIGHT = 1440


def filter_2k_images(
    target_dir: str | Path,
    *,
    target_width: int = TARGET_WIDTH,
    target_height: int = TARGET_HEIGHT,
    dry_run: bool = True,
) -> JobResult:
    """
    递归扫描目录，保留 target_width×target_height 的图片。
    dry_run=True 时仅统计与预览，不删除文件。
    """
    target_dir = Path(target_dir)
    if not target_dir.is_dir():
        return JobResult(ok=False, message=f"目录无效: {target_dir}")

    kept = 0
    to_remove: list[Path] = []
    errors: list[str] = []
    details: list[str] = []

    for root, _, files in os.walk(target_dir):
        for file in files:
            if not file.lower().endswith(COMMON_IMAGE_EXTENSIONS):
                continue

            file_path = Path(root) / file
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    if width == target_width and height == target_height:
                        kept += 1
                        details.append(
                            f"保留: {file_path.relative_to(target_dir)} ({width}x{height})"
                        )
                    else:
                        to_remove.append(file_path)
                        action = "将删除" if dry_run else "已删除"
                        details.append(
                            f"{action}: {file_path.relative_to(target_dir)} "
                            f"({width}x{height})"
                        )
                        if not dry_run:
                            img.close()
                            file_path.unlink(missing_ok=False)
            except Exception as e:
                errors.append(f"{file}: {e}")

    removed = len(to_remove)
    if dry_run:
        msg = f"预览：将保留 {kept} 张，将删除 {removed} 张（未实际删除）"
        ok = True
    else:
        msg = f"完成：保留 {kept} 张，已删除 {removed} 张"
        ok = removed > 0 or kept > 0

    return JobResult(
        ok=ok,
        message=msg,
        processed=removed if not dry_run else 0,
        skipped=kept,
        errors=errors,
        details=details,
        outputs=to_remove if dry_run else [],
    )
