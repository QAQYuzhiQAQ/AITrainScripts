"""图片格式互转（保持原始尺寸，不缩放）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image

from img_tools.common import (
    JobResult,
    ensure_dir,
    finalize_in_place_source,
    register_heif_opener,
    resolve_batch_output_dir,
)
from img_tools.convert import SUPPORTED_FORMATS

register_heif_opener()

TargetFormat = Literal["png", "jpeg", "webp", "bmp", "gif", "tiff"]

# 用户别名 → (扩展名, Pillow format)
FORMAT_MAP: dict[str, tuple[str, str]] = {
    "png": (".png", "PNG"),
    "jpeg": (".jpg", "JPEG"),
    "jpg": (".jpg", "JPEG"),
    "webp": (".webp", "WEBP"),
    "bmp": (".bmp", "BMP"),
    "gif": (".gif", "GIF"),
    "tiff": (".tif", "TIFF"),
    "tif": (".tif", "TIFF"),
}

INPUT_EXTENSIONS = SUPPORTED_FORMATS


@dataclass
class FormatConvertOptions:
    target_format: TargetFormat = "png"
    quality: int = 90
    recursive: bool = True
    in_place: bool = True
    skip_same_format: bool = False
    jpeg_background: tuple[int, int, int] = (255, 255, 255)


def normalize_target_format(raw: str) -> tuple[str, str, str]:
    """返回 (canonical_key, ext, pillow_format)。"""
    key = raw.strip().lower().lstrip(".")
    if key == "jpg":
        key = "jpeg"
    if key not in ("png", "jpeg", "webp", "bmp", "gif", "tiff"):
        raise ValueError(f"不支持的输出格式: {raw}")
    ext, pil_fmt = FORMAT_MAP[key if key != "jpeg" else "jpeg"]
    return key, ext, pil_fmt


def _collect_images(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        return sorted(
            p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS
        )
    return sorted(
        p for p in root.iterdir() if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS
    )


def _flatten_alpha(img: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    base = Image.new("RGB", img.size, bg)
    if img.mode in ("RGBA", "LA"):
        base.paste(img, mask=img.split()[-1])
        return base
    if img.mode == "P" and "transparency" in img.info:
        rgba = img.convert("RGBA")
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    return img.convert("RGB")


def _first_frame(img: Image.Image) -> Image.Image:
    if getattr(img, "is_animated", False):
        img.seek(0)
    return img.copy()


def _prepare_for_save(img: Image.Image, pil_format: str, opts: FormatConvertOptions) -> Image.Image:
    img = _first_frame(img)

    if pil_format == "JPEG":
        return _flatten_alpha(img, opts.jpeg_background)
    if pil_format == "PNG":
        return img.convert("RGBA") if img.mode not in ("RGB", "RGBA") else img
    if pil_format == "WEBP":
        return img.convert("RGBA") if img.mode != "RGBA" else img
    if pil_format == "BMP":
        return _flatten_alpha(img, opts.jpeg_background)
    if pil_format == "GIF":
        rgba = img.convert("RGBA")
        return rgba.convert("P", palette=Image.ADAPTIVE, colors=256)
    if pil_format == "TIFF":
        return img.convert("RGBA") if img.mode not in ("RGB", "RGBA") else img
    return img


def _save_kwargs(pil_format: str, quality: int) -> dict:
    q = max(1, min(100, quality))
    if pil_format == "JPEG":
        return {"quality": q, "optimize": True, "progressive": True}
    if pil_format == "WEBP":
        return {"quality": q, "method": 6}
    if pil_format == "PNG":
        return {"compress_level": 6, "optimize": True}
    if pil_format == "TIFF":
        return {"compression": "tiff_lzw"}
    return {}


def convert_image_format(img: Image.Image, out_path: Path, pil_format: str, opts: FormatConvertOptions) -> None:
    prepared = _prepare_for_save(img, pil_format, opts)
    ensure_dir(out_path.parent)
    tmp = out_path.with_suffix(out_path.suffix + ".part")
    try:
        prepared.save(tmp, format=pil_format, **_save_kwargs(pil_format, opts.quality))
        tmp.replace(out_path)
    finally:
        if tmp.exists() and tmp.resolve() != out_path.resolve():
            tmp.unlink(missing_ok=True)


def convert_images_format(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    options: FormatConvertOptions | None = None,
    target_format: str | None = None,
) -> JobResult:
    opts = options or FormatConvertOptions()
    if target_format is not None:
        opts = FormatConvertOptions(
            target_format=normalize_target_format(target_format)[0],  # type: ignore[arg-type]
            quality=opts.quality,
            recursive=opts.recursive,
            in_place=opts.in_place,
            skip_same_format=opts.skip_same_format,
            jpeg_background=opts.jpeg_background,
        )

    try:
        _, out_ext, pil_format = normalize_target_format(opts.target_format)
    except ValueError as e:
        return JobResult(ok=False, message=str(e), errors=[str(e)])

    input_root = Path(input_dir)
    if not input_root.is_dir():
        return JobResult(ok=False, message=f"输入目录不存在: {input_root}")

    output_root = resolve_batch_output_dir(
        input_root,
        output_dir,
        in_place=opts.in_place,
        subfolder_name="converted",
    )

    image_paths = _collect_images(input_root, opts.recursive)
    if not image_paths:
        return JobResult(ok=False, message="未找到可转换的图片")

    processed = 0
    skipped = 0
    errors: list[str] = []
    details: list[str] = []
    outputs: list[Path] = []

    for src in image_paths:
        rel = src.relative_to(input_root)
        out_path = output_root / rel.with_suffix(out_ext)

        if opts.skip_same_format and src.suffix.lower() == out_ext.lower():
            skipped += 1
            details.append(f"{rel}: 已是 {out_ext}，跳过")
            continue

        try:
            with Image.open(src) as img:
                animated = getattr(img, "is_animated", False)
                convert_image_format(img, out_path, pil_format, opts)
                finalize_in_place_source(src, out_path, in_place=opts.in_place)
                processed += 1
                outputs.append(out_path)
                note = "（动图仅首帧）" if animated and pil_format != "GIF" else ""
                details.append(f"{rel} → {out_path.name}{note}")
        except Exception as e:
            errors.append(f"{src.name}: {e}")

    ok = processed > 0 or skipped > 0
    fmt_label = opts.target_format.upper()
    dest_hint = "原文件夹（原地转换）" if opts.in_place else str(output_root)
    return JobResult(
        ok=ok and not (processed == 0 and errors and skipped == 0),
        message=(
            f"格式互转完成：{processed} 张 → {fmt_label}，跳过 {skipped} 张，{dest_hint}"
            if processed > 0
            else f"结束：{skipped} 张无需转换"
            if skipped > 0
            else "转换失败，未成功处理任何图片"
        ),
        processed=processed,
        skipped=skipped,
        errors=errors,
        details=details[:200],
        outputs=outputs,
    )
