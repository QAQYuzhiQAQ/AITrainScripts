"""批量重命名（前缀+补零 / 纯序号）。"""

from __future__ import annotations

import os
from pathlib import Path

from img_tools.common import JobResult

DEFAULT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")


def _sync_sidecars(folder: Path, old_stem: str, new_path: Path) -> list[str]:
    """将同名 .txt / .caption 与图片同步改名（须在图片 rename 之后调用）。"""
    notes: list[str] = []
    new_stem = new_path.stem
    for ext in (".txt", ".caption"):
        old_sidecar = folder / f"{old_stem}{ext}"
        if old_sidecar.is_file():
            new_sidecar = folder / f"{new_stem}{ext}"
            old_sidecar.rename(new_sidecar)
            notes.append(f"  联动: {old_stem}{ext} → {new_stem}{ext}")
    return notes


def batch_rename_numbered(
    folder_path: str | Path,
    *,
    prefix: str = "",
    start_num: int = 1,
    digits: int = 3,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    dry_run: bool = True,
    sync_captions: bool = False,
) -> JobResult:
    """批量重命名为 prefix + 补零编号 + 扩展名（自然排序）。"""
    try:
        import natsort
    except ImportError:
        return JobResult(ok=False, message="请先安装 natsort: pip install natsort")

    folder = Path(folder_path)
    if not folder.is_dir():
        return JobResult(ok=False, message=f"不是有效文件夹: {folder}")

    image_files = [
        f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in extensions
    ]
    image_files = natsort.natsorted(image_files)

    if not image_files:
        return JobResult(ok=False, message="文件夹中没有找到图片文件")

    details: list[str] = []
    errors: list[str] = []
    renamed = 0

    for i, old_path in enumerate(image_files, start=start_num):
        number_str = f"{i:0{digits}d}"
        new_name = f"{prefix}{number_str}{old_path.suffix}"
        new_path = old_path.parent / new_name
        details.append(f"{old_path.name} → {new_name}")

        if not dry_run:
            try:
                old_stem = old_path.stem
                os.rename(old_path, new_path)
                renamed += 1
                if sync_captions:
                    details.extend(_sync_sidecars(old_path.parent, old_stem, new_path))
            except Exception as e:
                errors.append(f"{old_path.name}: {e}")

    if dry_run:
        return JobResult(
            ok=True,
            message=f"预览 {len(image_files)} 个文件（未修改）",
            processed=0,
            skipped=len(image_files),
            details=details,
            errors=errors,
        )

    return JobResult(
        ok=renamed > 0 or not errors,
        message=f"成功重命名 {renamed} 个文件",
        processed=renamed,
        skipped=len(image_files) - renamed - len(errors),
        details=details,
        errors=errors,
    )


def rename_sequential(
    folder_path: str | Path,
    start_index: int,
    *,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    dry_run: bool = False,
    sync_captions: bool = False,
) -> JobResult:
    """将文件夹内图片重命名为「序号 + 扩展名」，从 start_index 递增。"""
    folder = Path(folder_path)
    if not folder.is_dir():
        return JobResult(ok=False, message=f"不是有效文件夹: {folder}")

    files = [f for f in os.listdir(folder) if f.lower().endswith(extensions)]
    current_index = start_index
    details: list[str] = []
    errors: list[str] = []
    renamed = 0
    skipped = 0

    for filename in files:
        name_part, extension = os.path.splitext(filename)
        if len(name_part) <= 0:
            skipped += 1
            details.append(f"跳过: {filename}")
            continue

        new_name = f"{current_index}{extension}"
        old_file = folder / filename
        new_file = folder / new_name

        if new_file.exists():
            skipped += 1
            details.append(f"跳过（目标已存在）: {filename} → {new_name}")
            continue

        details.append(f"{filename} → {new_name}")
        if not dry_run:
            try:
                old_stem = old_file.stem
                os.rename(old_file, new_file)
                renamed += 1
                if sync_captions:
                    details.extend(_sync_sidecars(old_file.parent, old_stem, new_file))
                current_index += 1
            except Exception as e:
                errors.append(f"{filename}: {e}")
        else:
            current_index += 1

    mode = "预览" if dry_run else "完成"
    return JobResult(
        ok=True,
        message=f"{mode}：共 {len(details)} 项",
        processed=renamed,
        skipped=skipped,
        details=details,
        errors=errors,
    )
