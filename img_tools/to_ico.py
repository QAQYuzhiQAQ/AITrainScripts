"""将 PNG / JPG 等图片批量转换为 Windows ICO 图标。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from img_tools.common import JobResult, ensure_dir, register_heif_opener
from img_tools.convert import SUPPORTED_FORMATS
from img_tools.resize import resize_fixed_canvas

register_heif_opener()

DEFAULT_ICO_SIZES = (16, 32, 48, 64, 128, 256)
ICO_INPUT_EXTENSIONS = SUPPORTED_FORMATS - {".ico"}


@dataclass
class ToIcoOptions:
    sizes: tuple[int, ...] = DEFAULT_ICO_SIZES
    max_canvas: int = 256
    recursive: bool = False


def parse_ico_sizes(raw: str | None) -> tuple[int, ...]:
    if not raw or not raw.strip():
        return DEFAULT_ICO_SIZES
    sizes: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
        except ValueError:
            continue
        if n > 0:
            sizes.append(n)
    return tuple(sorted(set(sizes))) if sizes else DEFAULT_ICO_SIZES


def _collect_images(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        return sorted(
            p
            for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in ICO_INPUT_EXTENSIONS
        )
    return sorted(
        p for p in root.iterdir() if p.is_file() and p.suffix.lower() in ICO_INPUT_EXTENSIONS
    )


def _save_as_ico(img: Image.Image, out_path: Path, sizes: tuple[int, ...], max_canvas: int) -> None:
    canvas = max(max_canvas, max(sizes))
    square = resize_fixed_canvas(img, canvas, canvas)
    if square.mode not in ("RGBA", "RGB"):
        square = square.convert("RGBA")
    ico_sizes = [(s, s) for s in sizes]
    ensure_dir(out_path.parent)
    square.save(out_path, format="ICO", sizes=ico_sizes)


def convert_images_to_ico(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    options: ToIcoOptions | None = None,
    sizes: str | None = None,
) -> JobResult:
    """
    将目录内图片转为 .ico（多尺寸嵌入同一文件）。

    output_dir 留空时，在与原图相同目录下生成同名 .ico。
    """
    opts = options or ToIcoOptions()
    if sizes is not None:
        opts = ToIcoOptions(
            sizes=parse_ico_sizes(sizes),
            max_canvas=opts.max_canvas,
            recursive=opts.recursive,
        )

    if not opts.sizes:
        return JobResult(ok=False, message="至少需要指定一个 ICO 尺寸")

    input_root = Path(input_dir)
    if not input_root.is_dir():
        return JobResult(ok=False, message=f"输入目录不存在: {input_root}")

    out_root = Path(output_dir).resolve() if output_dir else None
    if out_root:
        ensure_dir(out_root)

    image_paths = _collect_images(input_root, opts.recursive)
    if not image_paths:
        return JobResult(ok=False, message="未找到可转换的图片（支持 PNG/JPG/WebP 等，不含 .ico）")

    processed = 0
    skipped = 0
    errors: list[str] = []
    details: list[str] = []
    outputs: list[Path] = []

    for src in image_paths:
        rel = src.relative_to(input_root)
        if out_root:
            out_path = out_root / rel.with_suffix(".ico")
        else:
            out_path = src.with_suffix(".ico")

        try:
            with Image.open(src) as img:
                _save_as_ico(img, out_path, opts.sizes, opts.max_canvas)
            processed += 1
            outputs.append(out_path)
            size_text = ", ".join(str(s) for s in opts.sizes)
            details.append(f"{rel} → {out_path.name}（{size_text}px）")
        except Exception as e:
            errors.append(f"{src.name}: {e}")

    ok = processed > 0
    dest_hint = str(out_root) if out_root else "原图同目录"
    return JobResult(
        ok=ok,
        message=f"ICO 转换完成：{processed}/{len(image_paths)} 张，输出至 {dest_hint}"
        if ok
        else "ICO 转换失败，未成功处理任何图片",
        processed=processed,
        skipped=skipped,
        errors=errors,
        details=details[:200],
        outputs=outputs,
    )
