"""按目标文件大小压缩图片（质量 / 缩放二分）。"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image

from img_tools.common import JobResult, atomic_write_bytes, ensure_dir, finalize_in_place_source, register_heif_opener, resolve_batch_output_dir
from img_tools.convert import SUPPORTED_FORMATS

register_heif_opener()

CompressFormat = Literal["auto", "jpeg", "webp", "png"]
INPUT_EXTENSIONS = SUPPORTED_FORMATS

FORMAT_EXT = {"jpeg": ".jpg", "webp": ".webp", "png": ".png"}
EXT_ALIASES = {".jpg": ".jpg", ".jpeg": ".jpg", ".jfif": ".jpg", ".jpe": ".jpg", ".tif": ".tiff"}
MIN_QUALITY = 10
MAX_QUALITY = 95
MIN_SIDE = 32
SCALE_STEP = 0.85


@dataclass
class CompressOptions:
    max_bytes: int
    output_format: CompressFormat = "auto"
    recursive: bool = True
    in_place: bool = True
    min_quality: int = MIN_QUALITY
    max_quality: int = MAX_QUALITY


def parse_max_bytes(size: float, unit: str = "kb") -> int:
    """将用户输入转为字节上限。"""
    u = unit.strip().lower()
    if u in ("mb", "m"):
        return max(1, int(size * 1024 * 1024))
    if u in ("b", "byte", "bytes"):
        return max(1, int(size))
    return max(1, int(size * 1024))


def _pick_format(img: Image.Image, preference: CompressFormat) -> str:
    if preference != "auto":
        return preference
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        return "webp"
    return "jpeg"


def _normalize_ext(suffix: str) -> str:
    return EXT_ALIASES.get(suffix.lower(), suffix.lower())


def _first_frame(img: Image.Image) -> Image.Image:
    if getattr(img, "is_animated", False):
        img.seek(0)
    return img.copy()


def _prepare_for_format(img: Image.Image, fmt: str) -> Image.Image:
    if fmt == "jpeg":
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            return bg
        return img.convert("RGB")
    if fmt == "webp":
        return img.convert("RGBA") if img.mode != "RGBA" else img
    if fmt == "png":
        return img.convert("RGBA") if img.mode != "RGBA" else img
    return img


def _save_to_buffer(img: Image.Image, fmt: str, **kwargs) -> bytes:
    buf = BytesIO()
    save_fmt = {"jpeg": "JPEG", "webp": "WEBP", "png": "PNG"}[fmt]
    img.save(buf, format=save_fmt, **kwargs)
    return buf.getvalue()


def _encode_with_quality(img: Image.Image, fmt: str, quality: int) -> bytes:
    if fmt == "jpeg":
        return _save_to_buffer(img, fmt, quality=quality, optimize=True, progressive=True)
    if fmt == "webp":
        return _save_to_buffer(img, fmt, quality=quality, method=6)
    level = max(0, min(9, 9 - int((quality - MIN_QUALITY) / (MAX_QUALITY - MIN_QUALITY) * 9)))
    return _save_to_buffer(img, fmt, compress_level=level, optimize=True)


def _best_bytes_for_quality(img: Image.Image, fmt: str, max_bytes: int, opts: CompressOptions) -> bytes | None:
    lo, hi = opts.min_quality, opts.max_quality
    best: bytes | None = None

    while lo <= hi:
        mid = (lo + hi) // 2
        data = _encode_with_quality(img, fmt, mid)
        if len(data) <= max_bytes:
            best = data
            lo = mid + 1
        else:
            hi = mid - 1

    return best


def compress_single_image(
    img: Image.Image,
    max_bytes: int,
    *,
    output_format: CompressFormat = "auto",
    opts: CompressOptions | None = None,
) -> tuple[bytes, str, dict[str, int | float | str]]:
    """返回 (数据, 格式名, 元信息)。"""
    opts = opts or CompressOptions(max_bytes=max_bytes, output_format=output_format)
    img = _first_frame(img)
    fmt = _pick_format(img, output_format)
    working = _prepare_for_format(img, fmt)
    scale = 1.0
    meta: dict[str, int | float | str] = {"format": fmt}

    while True:
        w, h = working.size
        if w < MIN_SIDE or h < MIN_SIDE:
            break

        data = _best_bytes_for_quality(working, fmt, max_bytes, opts)
        if data is not None:
            meta["quality_search"] = "ok"
            meta["scale"] = round(scale, 4)
            meta["width"] = working.size[0]
            meta["height"] = working.size[1]
            meta["bytes"] = len(data)
            return data, fmt, meta

        scale *= SCALE_STEP
        new_w = max(MIN_SIDE, int(img.size[0] * scale))
        new_h = max(MIN_SIDE, int(img.size[1] * scale))
        if new_w == working.size[0] and new_h == working.size[1]:
            break
        working = _prepare_for_format(
            img.resize((new_w, new_h), Image.Resampling.LANCZOS),
            fmt,
        )

    data = _encode_with_quality(working, fmt, opts.min_quality)
    meta["quality_search"] = "min_fallback"
    meta["scale"] = round(scale, 4)
    meta["width"] = working.size[0]
    meta["height"] = working.size[1]
    meta["bytes"] = len(data)
    return data, fmt, meta


def _collect_images(root: Path, recursive: bool) -> list[Path]:
    def ok(p: Path) -> bool:
        if not p.is_file() or p.name.endswith(".part"):
            return False
        return p.suffix.lower() in INPUT_EXTENSIONS

    if recursive:
        return sorted(p for p in root.rglob("*") if ok(p))
    return sorted(p for p in root.iterdir() if ok(p))


def _format_size(num: int) -> str:
    if num >= 1024 * 1024:
        return f"{num / (1024 * 1024):.2f} MB"
    if num >= 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num} B"


def compress_images(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    options: CompressOptions | None = None,
    max_bytes: int | None = None,
) -> JobResult:
    if options is None:
        if max_bytes is None:
            return JobResult(ok=False, message="未指定目标大小")
        options = CompressOptions(max_bytes=max_bytes)

    input_root = Path(input_dir)
    if not input_root.is_dir():
        return JobResult(ok=False, message=f"输入目录不存在: {input_root}")

    out_root = resolve_batch_output_dir(
        input_root,
        output_dir,
        in_place=options.in_place,
        subfolder_name="compressed",
    )

    image_paths = _collect_images(input_root, options.recursive)
    if not image_paths:
        return JobResult(ok=False, message="未找到可压缩的图片")

    processed = 0
    skipped = 0
    errors: list[str] = []
    details: list[str] = []
    outputs: list[Path] = []
    target_text = _format_size(options.max_bytes)

    for src in image_paths:
        rel = src.relative_to(input_root)
        src_size = src.stat().st_size

        try:
            with Image.open(src) as img:
                img.load()
                fmt_hint = _pick_format(img, options.output_format)
                ext = FORMAT_EXT[fmt_hint]
                out_path = out_root / rel.with_suffix(ext)

                data, fmt, meta = compress_single_image(
                    img,
                    options.max_bytes,
                    output_format=options.output_format,
                    opts=options,
                )
                atomic_write_bytes(out_path, data)
                finalize_in_place_source(src, out_path, in_place=options.in_place)
                processed += 1
                outputs.append(out_path)
                converted = _normalize_ext(src.suffix) != _normalize_ext(out_path.suffix)
                fmt_note = f" → {fmt.upper()}" if converted or _normalize_ext(src.suffix) != ext else ""
                warn = "（未达目标，已用最低质量/最小尺寸）" if meta.get("quality_search") == "min_fallback" and len(data) > options.max_bytes else ""
                details.append(
                    f"{rel} → {out_path.name}{fmt_note}: {_format_size(src_size)} → {_format_size(len(data))}"
                    f" [{meta['width']}×{meta['height']}]{warn}"
                )
        except Exception as e:
            errors.append(f"{src.name}: {e}")

    ok = processed > 0
    dest_hint = "原文件夹（原地压缩）" if options.in_place else str(out_root)
    fmt_label = options.output_format.upper() if options.output_format != "auto" else "自动(JPEG/WebP)"
    return JobResult(
        ok=ok and not (processed == 0 and errors),
        message=(
            f"压缩完成：共处理 {processed} 张 → {fmt_label}，目标 ≤ {target_text}，{dest_hint}"
            if processed > 0
            else "压缩失败，未成功处理任何图片"
        ),
        processed=processed,
        skipped=skipped,
        errors=errors,
        details=details[:200],
        outputs=outputs,
    )
