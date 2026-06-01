"""多格式转 PNG、智能面积缩放、按目录 0.png 重命名。"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path

from PIL import Image

from img_tools.common import JobResult, ensure_dir, register_heif_opener

register_heif_opener()

SUPPORTED_FORMATS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tiff",
    ".tif",
    ".ico",
    ".jfif",
    ".jpe",
    ".heic",
    ".heif",
    ".jp2",
}


def get_optimal_target_size(orig_w: int, orig_h: int, target_area: int) -> tuple[int, int]:
    """根据原图比例，计算最接近 target_area 且长宽均为 64 倍数的尺寸。"""
    if orig_w <= 0 or orig_h <= 0:
        return 64, 64

    aspect_ratio = orig_w / orig_h
    ideal_h = math.sqrt(target_area / aspect_ratio)
    ideal_w = ideal_h * aspect_ratio
    target_w = max(64, round(ideal_w / 64) * 64)
    target_h = max(64, round(ideal_h / 64) * 64)
    return target_w, target_h


def resize_with_padding(img: Image.Image, target_area: int) -> Image.Image | None:
    """动态匹配 64 倍数尺寸，保持比例缩放并在透明背景上居中。"""
    orig_w, orig_h = img.size
    if orig_w <= 0 or orig_h <= 0:
        return None

    target_width, target_height = get_optimal_target_size(orig_w, orig_h, target_area)
    scale = min(target_width / orig_w, target_height / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    paste_x = (target_width - new_w) // 2
    paste_y = (target_height - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))
    return canvas


def rename_files_in_each_dir(output_root: str | Path) -> None:
    """在每个文件夹内独立重命名为 0.png, 1.png, ..."""
    output_root = Path(output_root)
    ts = int(time.time())
    for root, _, _ in os.walk(output_root):
        current_dir = Path(root)
        png_files = sorted(current_dir.glob("*.png"), key=lambda p: p.name)
        if not png_files:
            continue

        temp_mappings: list[tuple[Path, int]] = []
        for i, f in enumerate(png_files):
            temp_path = current_dir / f"__tmp_{ts}_{i}.png"
            f.rename(temp_path)
            temp_mappings.append((temp_path, i))

        for temp_path, i in temp_mappings:
            temp_path.rename(current_dir / f"{i}.png")


def process_all(
    target_path: str | Path,
    output_path: str | Path,
    target_area: int,
    recursive: bool = True,
    *,
    rename_output: bool = True,
) -> JobResult:
    """
    批量转换：多格式 → PNG，智能缩放填充，可选递归，可选按目录重命名。
    target_area 通常由基准宽×高得出（如 1024×1024 → 1048576）。
    """
    target_root = Path(target_path)
    output_root = Path(output_path)

    if not target_root.exists():
        return JobResult(ok=False, message="目标路径不存在")

    if recursive:
        all_files = []
        for root, _, files in os.walk(target_root):
            for name in files:
                all_files.append(Path(root) / name)
    else:
        all_files = [f for f in target_root.iterdir() if f.is_file()]

    processed_list: list[Path] = []
    errors: list[str] = []
    details: list[str] = []

    for file_path in all_files:
        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            continue

        relative_path = file_path.relative_to(target_root)
        target_out_file = output_root / relative_path.with_suffix(".png")
        ensure_dir(target_out_file.parent)

        try:
            with Image.open(file_path) as img:
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                result = resize_with_padding(img, target_area)
                if result:
                    result.save(target_out_file, "PNG")
                    processed_list.append(target_out_file)
                    details.append(
                        f"转换: {relative_path} → {target_out_file.relative_to(output_root)}"
                    )
        except Exception as e:
            errors.append(f"{file_path.name}: {e}")

    if processed_list and rename_output:
        try:
            rename_files_in_each_dir(output_root)
            details.append("已对各输出目录执行 0.png, 1.png... 重命名")
        except Exception as e:
            errors.append(f"重命名环节出错: {e}")

    if not processed_list:
        return JobResult(
            ok=False,
            message="未找到可处理的图片文件",
            errors=errors,
            details=details,
        )

    return JobResult(
        ok=True,
        message=f"成功处理 {len(processed_list)} 张图片",
        processed=len(processed_list),
        errors=errors,
        details=details,
        outputs=processed_list,
    )
