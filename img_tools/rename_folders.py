"""子文件夹批量重命名（Kohya 训练目录等）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from img_tools.common import JobResult


@dataclass
class SubfolderRenameOptions:
    prefix: str = "10_"
    remove_spaces: bool = True
    recursive: bool = False
    dry_run: bool = True


def transform_subfolder_name(name: str, *, prefix: str = "10_", remove_spaces: bool = True) -> str:
    """去掉空格并加前缀（已有前缀则不重复添加）。"""
    cleaned = name.replace(" ", "") if remove_spaces else name
    if prefix and not cleaned.startswith(prefix):
        cleaned = f"{prefix}{cleaned}"
    return cleaned


def _collect_target_dirs(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        dirs = [p for p in root.rglob("*") if p.is_dir()]
        dirs.sort(key=lambda p: len(p.parts), reverse=True)
        return dirs
    return sorted(p for p in root.iterdir() if p.is_dir())


def rename_subfolders(
    root_dir: str | Path,
    *,
    options: SubfolderRenameOptions | None = None,
    prefix: str | None = None,
    remove_spaces: bool | None = None,
    recursive: bool | None = None,
    dry_run: bool | None = None,
) -> JobResult:
    """
    重命名 root_dir 下的子文件夹（默认仅一层）。

    规则：去掉文件夹名中的空格，并在名前加 prefix（默认 10_）。
    """
    opts = options or SubfolderRenameOptions()
    if prefix is not None:
        opts = SubfolderRenameOptions(
            prefix=prefix,
            remove_spaces=opts.remove_spaces if remove_spaces is None else remove_spaces,
            recursive=opts.recursive if recursive is None else recursive,
            dry_run=opts.dry_run if dry_run is None else dry_run,
        )
    elif remove_spaces is not None or recursive is not None or dry_run is not None:
        opts = SubfolderRenameOptions(
            prefix=opts.prefix,
            remove_spaces=opts.remove_spaces if remove_spaces is None else remove_spaces,
            recursive=opts.recursive if recursive is None else recursive,
            dry_run=opts.dry_run if dry_run is None else dry_run,
        )

    root = Path(root_dir)
    if not root.is_dir():
        return JobResult(ok=False, message=f"目录不存在: {root}")

    targets = _collect_target_dirs(root, opts.recursive)
    if not targets:
        return JobResult(ok=False, message="未找到可重命名的子文件夹")

    details: list[str] = []
    errors: list[str] = []
    processed = 0
    skipped = 0

    for folder in targets:
        old_name = folder.name
        new_name = transform_subfolder_name(
            old_name,
            prefix=opts.prefix,
            remove_spaces=opts.remove_spaces,
        )
        if new_name == old_name:
            skipped += 1
            details.append(f"{folder.relative_to(root)}: 无需变更")
            continue

        new_path = folder.parent / new_name
        rel_old = folder.relative_to(root)

        if new_path.exists():
            errors.append(f"{rel_old}: 目标已存在 → {new_name}")
            continue

        details.append(f"{rel_old} → {new_path.relative_to(root)}")
        if not opts.dry_run:
            try:
                folder.rename(new_path)
                processed += 1
            except OSError as e:
                errors.append(f"{rel_old}: {e}")
        else:
            processed += 1

    mode = "预览" if opts.dry_run else "完成"
    scope = "全部层级" if opts.recursive else "直接子文件夹"
    return JobResult(
        ok=processed > 0 or (skipped > 0 and not errors),
        message=f"子文件夹重命名{mode}（{scope}）：变更 {processed} 个，跳过 {skipped} 个",
        processed=0 if opts.dry_run else processed,
        skipped=skipped if opts.dry_run else skipped,
        errors=errors,
        details=details[:300],
    )
