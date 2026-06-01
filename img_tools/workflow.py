"""LoRA 数据准备一键工作流：缩放/转换 → 输出 → 批量重命名。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from PIL import Image

import os
import shutil

from img_tools.common import JobResult, ensure_dir

from img_tools.convert import SUPPORTED_FORMATS, process_all
from img_tools.rename import batch_rename_numbered, rename_sequential
from img_tools.resize import resize_fixed_canvas


class ResizeMode(str, Enum):
    """缩放模式。"""

    AREA_64 = "area_64"
    """等效像素面积，输出长宽为 64 的倍数，等比缩放 + 透明居中（不拉伸）。"""

    FIXED_CANVAS = "fixed_canvas"
    """固定宽×高画布，等比缩放 + 透明居中补足。"""


class RenameMode(str, Enum):
    NONE = "none"
    NUMBERED = "numbered"
    SEQUENTIAL = "sequential"


@dataclass
class WorkflowRenameOptions:
    mode: RenameMode = RenameMode.NUMBERED
    prefix: str = ""
    start_num: int = 1
    digits: int = 4
    start_index: int = 1
    sync_captions: bool = True


def _collect_image_files(target_root: Path, recursive: bool) -> list[Path]:
    if recursive:
        return [
            Path(root) / name
            for root, _, files in os.walk(target_root)
            for name in files
            if (Path(root) / name).suffix.lower() in SUPPORTED_FORMATS
        ]
    return [
        f
        for f in target_root.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
    ]


def process_all_fixed_canvas(
    target_path: str | Path,
    output_path: str | Path,
    canvas_width: int,
    canvas_height: int,
    recursive: bool = False,
) -> JobResult:
    """多格式 → PNG，固定宽×高透明画布居中（等比缩放，不拉伸）。"""
    target_root = Path(target_path)
    output_root = Path(output_path)

    if not target_root.exists():
        return JobResult(ok=False, message="来源路径不存在")

    all_files = _collect_image_files(target_root, recursive)
    processed_list: list[Path] = []
    errors: list[str] = []
    details: list[str] = []

    for file_path in all_files:
        relative_path = file_path.relative_to(target_root)
        target_out_file = output_root / relative_path.with_suffix(".png")
        ensure_dir(target_out_file.parent)

        try:
            with Image.open(file_path) as img:
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                result = resize_fixed_canvas(img, canvas_width, canvas_height)
                result.save(target_out_file, "PNG")
                processed_list.append(target_out_file)
                details.append(
                    f"转换: {relative_path} → {target_out_file.relative_to(output_root)} "
                    f"({canvas_width}×{canvas_height})"
                )
        except Exception as e:
            errors.append(f"{file_path.name}: {e}")

    if not processed_list:
        return JobResult(
            ok=False,
            message="未找到可处理的图片文件",
            errors=errors,
            details=details,
        )

    return JobResult(
        ok=True,
        message=f"成功处理 {len(processed_list)} 张（固定画布 {canvas_width}×{canvas_height}）",
        processed=len(processed_list),
        errors=errors,
        details=details,
        outputs=processed_list,
    )


def _copy_sidecars_from_source(
    source_root: Path,
    output_root: Path,
    recursive: bool,
) -> int:
    """将来源目录中与图片同名的 .txt / .caption 复制到输出目录对应 PNG 旁。"""
    copied = 0
    for src in _collect_image_files(source_root, recursive):
        rel = src.relative_to(source_root)
        out_png = output_root / rel.with_suffix(".png")
        if not out_png.is_file():
            continue
        for ext in (".txt", ".caption"):
            sidecar = src.with_suffix(ext)
            if sidecar.is_file():
                shutil.copy2(sidecar, out_png.with_suffix(ext))
                copied += 1
    return copied


def _rename_targets_for_output(output_root: Path, recursive: bool) -> list[Path]:
    if not recursive:
        return [output_root]
    dirs = {p.parent for p in output_root.rglob("*.png") if p.is_file()}
    return sorted(dirs) if dirs else [output_root]


def _apply_rename(
    output_root: Path,
    rename: WorkflowRenameOptions,
    *,
    recursive: bool,
    dry_run: bool = False,
) -> JobResult:
    if rename.mode == RenameMode.NONE:
        return JobResult(ok=True, message="已跳过重命名步骤")

    dirs = _rename_targets_for_output(output_root, recursive)
    total_renamed = 0
    all_details: list[str] = []
    all_errors: list[str] = []

    for folder in dirs:
        if rename.mode == RenameMode.NUMBERED:
            result = batch_rename_numbered(
                folder,
                prefix=rename.prefix,
                start_num=rename.start_num,
                digits=rename.digits,
                dry_run=dry_run,
                sync_captions=rename.sync_captions,
            )
        else:
            result = rename_sequential(
                folder,
                rename.start_index,
                dry_run=dry_run,
                sync_captions=rename.sync_captions,
            )

        if folder != output_root:
            all_details.append(f"--- 目录: {folder.relative_to(output_root)} ---")
        all_details.extend(result.details)
        all_errors.extend(result.errors)
        total_renamed += result.processed

    ok = not all_errors or total_renamed > 0
    return JobResult(
        ok=ok,
        message=f"重命名完成：{total_renamed} 个文件"
        if not dry_run
        else f"重命名预览：{len(all_details)} 项",
        processed=total_renamed,
        errors=all_errors,
        details=all_details,
    )


def run_prepare_workflow(
    source_dir: str | Path,
    output_dir: str | Path,
    target_width: int,
    target_height: int,
    resize_mode: ResizeMode | Literal["area_64", "fixed_canvas"],
    *,
    recursive: bool = False,
    rename: WorkflowRenameOptions | None = None,
) -> JobResult:
    """
    一键工作流：
    1. 读取 source_dir 中的图片
    2. 按 resize_mode 处理并写入 output_dir（PNG）
    3. 按 rename 配置对 output_dir 内图片批量重命名

    resize_mode:
      - area_64: 目标面积 = target_width × target_height，输出 64 倍数画布
      - fixed_canvas: 输出严格为 target_width × target_height
    """
    rename = rename or WorkflowRenameOptions()
    if isinstance(resize_mode, str):
        resize_mode = ResizeMode(resize_mode)

    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    ensure_dir(output_dir)

    if target_width < 1 or target_height < 1:
        return JobResult(ok=False, message="宽和高必须为正整数")

    # --- 步骤 2–3：图像处理 ---
    if resize_mode == ResizeMode.AREA_64:
        target_area = target_width * target_height
        process_result = process_all(
            source_dir,
            output_dir,
            target_area,
            recursive,
            rename_output=False,
        )
        mode_label = f"等效面积 {target_width}×{target_height}（64 倍数画布）"
    else:
        process_result = process_all_fixed_canvas(
            source_dir,
            output_dir,
            target_width,
            target_height,
            recursive,
        )
        mode_label = f"固定画布 {target_width}×{target_height}"

    if not process_result.ok and process_result.processed == 0:
        process_result.message = f"[处理失败] {process_result.message}"
        return process_result

    sidecar_copied = _copy_sidecars_from_source(source_dir, output_dir, recursive)
    if sidecar_copied:
        process_result.details.append(f"已复制 {sidecar_copied} 个配对标注文件到输出目录")

    # --- 步骤 4：重命名 ---
    rename_result = _apply_rename(
        output_dir,
        rename,
        recursive=recursive,
        dry_run=False,
    )

    combined_details = [
        f"=== 图像处理（{mode_label}）===",
        process_result.message,
        *process_result.details[:100],
    ]
    if len(process_result.details) > 100:
        combined_details.append("…（处理详情已截断）")
    combined_details.append("=== 批量重命名 ===")
    combined_details.extend(rename_result.details[:100])

    combined_errors = list(process_result.errors) + list(rename_result.errors)
    ok = process_result.ok and rename_result.ok

    return JobResult(
        ok=ok,
        message=(
            f"工作流完成：处理 {process_result.processed} 张，"
            f"重命名 {rename_result.processed} 个"
        ),
        processed=process_result.processed,
        skipped=rename_result.skipped,
        errors=combined_errors,
        details=combined_details,
        outputs=process_result.outputs,
    )
