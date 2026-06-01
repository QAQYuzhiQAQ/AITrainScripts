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
        print(f"❌ {err}")
