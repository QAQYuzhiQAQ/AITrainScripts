"""共享类型与工具函数。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class JobResult:
    """批处理任务统一返回结构。"""

    ok: bool
    message: str
    processed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    outputs: list[Path] = field(default_factory=list)


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def resolve_batch_output_dir(
    input_root: Path,
    output_dir: str | Path | None,
    *,
    in_place: bool,
    subfolder_name: str,
) -> Path:
    """确定批量处理的输出根目录。"""
    if in_place:
        return input_root
    if output_dir:
        out = Path(output_dir)
        ensure_dir(out)
        return out
    out = input_root / subfolder_name
    ensure_dir(out)
    return out


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """原子写入，避免原地覆盖时损坏原文件。"""
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".part")
    try:
        tmp.write_bytes(data)
        tmp.replace(path)
    finally:
        if tmp.exists() and tmp.resolve() != path.resolve():
            tmp.unlink(missing_ok=True)


def finalize_in_place_source(src: Path, out_path: Path, *, in_place: bool) -> None:
    """原地模式下，扩展名变更后删除原文件。"""
    if not in_place:
        return
    if src.resolve() == out_path.resolve():
        return
    if src.is_file():
        src.unlink()


def register_heif_opener() -> bool:
    """注册 HEIC/HEIF 支持；成功返回 True。"""
    try:
        from pillow_heif import register_heif_opener as _register

        _register()
        return True
    except ImportError:
        return False


COMMON_IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
)


def print_job_result(result: JobResult) -> None:
    """CLI 脚本打印 JobResult 的简易输出。"""
    print(result.message)
    for line in result.details:
        print(line)
    for err in result.errors:
        print(f"[错误] {err}")
