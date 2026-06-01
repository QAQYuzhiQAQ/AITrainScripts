"""固定尺寸画布居中缩放。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from img_tools.common import JobResult, ensure_dir


def resize_fixed_canvas(
    img: Image.Image,
    canvas_width: int = 1024,
    canvas_height: int | None = None,
) -> Image.Image:
    """等比缩放使图片完整放入 canvas_width×canvas_height，透明背景居中。"""
    if canvas_height is None:
        canvas_height = canvas_width

    w, h = img.size
    if w <= 0 or h <= 0:
        raise ValueError("无效图片尺寸")

    scale = min(canvas_width / w, canvas_height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    if resized.mode != "RGBA":
        resized = resized.convert("RGBA")

    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    offset_x = (canvas_width - new_w) // 2
    offset_y = (canvas_height - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas


def resize_png_center_batch(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    canvas_width: int = 1024,
    canvas_height: int | None = None,
    canvas_size: int | None = None,
    recursive: bool = False,
) -> JobResult:
    """
    将目录内 PNG 缩放并居中到指定宽高透明画布。
    canvas_size 若提供则作为正方形边长（兼容旧调用）。
    默认 output_dir 为 input_dir/new。
    """
    if canvas_size is not None:
        canvas_width = canvas_size
        canvas_height = canvas_size
    if canvas_height is None:
        canvas_height = canvas_width

    input_root = Path(input_dir)
    if not input_root.is_dir():
        return JobResult(ok=False, message=f"输入目录无效: {input_root}")

    out_root = Path(output_dir) if output_dir else input_root / "new"
    ensure_dir(out_root)

    if recursive:
        candidates = [p for p in input_root.rglob("*.png") if p.is_file()]
    else:
        candidates = [
            p for p in input_root.iterdir() if p.is_file() and p.suffix.lower() == ".png"
        ]

    processed_list: list[Path] = []
    errors: list[str] = []
    details: list[str] = []

    for file_path in candidates:
        try:
            rel = file_path.relative_to(input_root)
            out_path = out_root / rel
            ensure_dir(out_path.parent)

            with Image.open(file_path) as img:
                canvas = resize_fixed_canvas(img, canvas_width, canvas_height)
                canvas.save(out_path, "PNG")
                processed_list.append(out_path)
                details.append(f"{rel} → {out_path.relative_to(out_root)}")
        except Exception as e:
            errors.append(f"{file_path.name}: {e}")

    if not processed_list:
        return JobResult(
            ok=False,
            message="未找到 PNG 文件",
            errors=errors,
            details=details,
        )

    return JobResult(
        ok=True,
        message=f"成功处理 {len(processed_list)} 张 PNG（画布 {canvas_width}×{canvas_height}）",
        processed=len(processed_list),
        errors=errors,
        details=details,
        outputs=processed_list,
    )
