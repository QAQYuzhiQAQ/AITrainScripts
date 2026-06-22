"""LoRA 角色训练目录路径约定。"""

from __future__ import annotations

from pathlib import Path

from img_tools.common import COMMON_IMAGE_EXTENSIONS


def concept_dir_name(repeat_count: int) -> str:
    return f"{repeat_count}_output"


def resolve_paths(character_root: str | Path, repeat_count: int = 10) -> dict[str, Path]:
    root = Path(character_root).resolve()
    output = root / "output"
    return {
        "root": root,
        "res": root / "res",
        "output": output,
        "concept": output / concept_dir_name(repeat_count),
    }


def ensure_structure(character_root: str | Path, repeat_count: int = 10) -> dict[str, Path]:
    paths = resolve_paths(character_root, repeat_count)
    paths["res"].mkdir(parents=True, exist_ok=True)
    paths["output"].mkdir(parents=True, exist_ok=True)
    paths["concept"].mkdir(parents=True, exist_ok=True)
    return paths


def is_raw_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in COMMON_IMAGE_EXTENSIONS


def list_root_raw_images(character_root: Path) -> list[Path]:
    """characterABC 根目录下的原始图片（不含 res/output 子目录）。"""
    reserved = {"res", "output"}
    images: list[Path] = []
    for item in character_root.iterdir():
        if item.name in reserved or item.name.startswith("."):
            continue
        if is_raw_image_file(item):
            images.append(item)
    return sorted(images)
