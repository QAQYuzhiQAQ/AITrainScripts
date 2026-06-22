"""本机目录浏览（限制在用户主目录内）。"""

from __future__ import annotations

from pathlib import Path


def _home() -> Path:
    return Path.home().resolve()


def _clamp_to_home(path: Path) -> Path:
    home = _home()
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(home)
        return resolved
    except ValueError:
        return home


def browse_directory(path: str | None = None) -> dict:
    """
    列出目录下的子文件夹。
    path 为空时从用户主目录开始；禁止访问主目录之外的路径。
    """
    home = _home()
    current = _clamp_to_home(Path(path) if path else home)

    if not current.is_dir():
        current = current.parent if current.parent.is_dir() else home

    entries: list[dict] = []
    if current != home:
        parent = _clamp_to_home(current.parent)
        entries.append({"name": "..", "path": str(parent), "is_dir": True})

    try:
        children = sorted(current.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        children = []

    for item in children:
        if item.name.startswith("."):
            continue
        try:
            if item.is_dir():
                entries.append(
                    {"name": item.name, "path": str(item.resolve()), "is_dir": True}
                )
        except OSError:
            continue

    return {"current": str(current), "home": str(home), "entries": entries}


_MEDIA_EXT = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".heic",
    ".heif",
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
}


def browse_media(path: str | None = None) -> dict:
    """列出目录下的子文件夹与常见图片/音视频文件（限制在用户主目录内）。"""
    home = _home()
    current = _clamp_to_home(Path(path) if path else home)

    if not current.is_dir():
        current = current.parent if current.parent.is_dir() else home

    entries: list[dict] = []
    if current != home:
        parent = _clamp_to_home(current.parent)
        entries.append({"name": "..", "path": str(parent), "is_dir": True})

    dirs: list[Path] = []
    files: list[Path] = []
    try:
        children = sorted(current.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        children = []

    for item in children:
        if item.name.startswith("."):
            continue
        try:
            if item.is_dir():
                dirs.append(item)
            elif item.is_file() and item.suffix.lower() in _MEDIA_EXT:
                files.append(item)
        except OSError:
            continue

    for item in dirs:
        entries.append({"name": item.name, "path": str(item.resolve()), "is_dir": True})
    for item in files:
        entries.append({"name": item.name, "path": str(item.resolve()), "is_dir": False})

    return {"current": str(current), "home": str(home), "entries": entries}
