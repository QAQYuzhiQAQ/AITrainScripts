"""将本地路径转为 Seedance API 可接受的 data URI。"""

from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path

ReferenceType = str

MAX_BYTES: dict[str, int] = {
    "image_url": 30 * 1024 * 1024,
    "video_url": 50 * 1024 * 1024,
    "audio_url": 15 * 1024 * 1024,
}

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".tif", ".tiff"}
_VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

_API_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})


def guess_ref_type(path: Path) -> ReferenceType | None:
    ext = path.suffix.lower()
    if ext in _IMAGE_EXT:
        return "image_url"
    if ext in _VIDEO_EXT:
        return "video_url"
    if ext in _AUDIO_EXT:
        return "audio_url"
    return None


def bytes_to_data_uri(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def is_remote_or_embedded(url: str) -> bool:
    lower = url.strip().lower()
    return lower.startswith(("http://", "https://", "data:"))


def normalize_local_path_input(url: str) -> Path:
    """清理用户粘贴的本机路径并展开为绝对路径。"""
    raw = url.strip()
    raw = raw.strip('"').strip("'").strip("`")
    raw = raw.replace("\u00a0", " ").strip()
    if raw.lower().startswith("file://"):
        raw = raw[7:]
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return path.expanduser().resolve()


def resolve_local_media_path(url: str, *, label: str | None = None) -> Path:
    """解析本机路径；不存在时抛出带说明的 ValueError。"""
    prefix = f"{label}：" if label else ""
    if not url.strip():
        raise ValueError(f"{prefix}路径为空")

    path = normalize_local_path_input(url)
    if path.is_file():
        return path

    hint = (
        f"{prefix}找不到本地文件：{url.strip()}\n"
        f"已尝试解析为：{path}\n"
        "请确认路径完整且文件存在（建议使用绝对路径，如 /Users/你/Pictures/photo.jpg），"
        "或使用拖放/「浏览」选择文件。"
    )
    raise ValueError(hint)


def validate_local_media(url: str, ref_type: ReferenceType) -> dict[str, object]:
    """校验本机媒体文件可读（不读取完整 base64）。"""
    path = resolve_local_media_path(url, label="参考素材")
    detected = guess_ref_type(path)
    if detected and detected != ref_type:
        type_names = {
            "image_url": "图片",
            "video_url": "视频",
            "audio_url": "音频",
        }
        raise ValueError(
            f"参考素材：文件扩展名像是{type_names.get(detected, detected)}，"
            f"但当前类型选的是{type_names.get(ref_type, ref_type)}，请修改类型或换文件。"
        )

    size = path.stat().st_size
    max_bytes = MAX_BYTES.get(ref_type, MAX_BYTES["image_url"])
    if size > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        actual_mb = size / (1024 * 1024)
        raise ValueError(
            f"参考素材：文件过大（{actual_mb:.1f} MB），{ref_type} 上限 {limit_mb:.0f} MB：{path.name}"
        )

    return {
        "ok": True,
        "path": str(path),
        "name": path.name,
        "size": size,
        "ref_type": ref_type,
    }


def _prepare_image_bytes(path: Path) -> tuple[bytes, str]:
    """读取图片；HEIC 等方舟不支持的格式转为 JPEG。"""
    mime, _ = mimetypes.guess_type(str(path))
    ext = path.suffix.lower()
    needs_convert = ext in {".heic", ".heif", ".bmp", ".tif", ".tiff"} or (
        mime not in _API_IMAGE_MIMES if mime else ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    )

    if not needs_convert and mime in _API_IMAGE_MIMES:
        return path.read_bytes(), mime or "image/jpeg"

    try:
        from PIL import Image

        from img_tools.common import register_heif_opener

        register_heif_opener()
        with Image.open(path) as im:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGB")
            elif im.mode != "RGB":
                im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=92)
            return buf.getvalue(), "image/jpeg"
    except ImportError as e:
        raise ValueError(
            f"无法读取图片 {path.name}，请安装 Pillow 或将文件转为 JPG/PNG 后重试。"
        ) from e
    except Exception as e:
        raise ValueError(f"无法读取图片 {path.name}：{e}") from e


def file_to_data_uri(path: Path, ref_type: ReferenceType) -> str:
    max_bytes = MAX_BYTES.get(ref_type, MAX_BYTES["image_url"])

    if ref_type == "image_url":
        data, mime = _prepare_image_bytes(path)
    else:
        data = path.read_bytes()
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "application/octet-stream"

    if len(data) > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        actual_mb = len(data) / (1024 * 1024)
        raise ValueError(
            f"文件过大（{actual_mb:.1f} MB），{ref_type} 上限 {limit_mb:.0f} MB：{path.name}"
        )
    return bytes_to_data_uri(data, mime)


def resolve_reference_url(
    url: str,
    ref_type: ReferenceType,
    *,
    label: str | None = None,
) -> str:
    """http(s)/data URI 原样返回；本地路径读取为 data URI。"""
    url = url.strip()
    if not url:
        return url
    if is_remote_or_embedded(url):
        return url

    path = resolve_local_media_path(url, label=label)
    return file_to_data_uri(path.resolve(), ref_type)
