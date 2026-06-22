"""MP4 批量提取音频为 MP3（依赖系统 ffmpeg）。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from img_tools.common import JobResult, ensure_dir

_MP4_SUFFIX = {".mp4", ".m4v", ".mov"}


def is_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _collect_mp4_files(root: Path, *, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in _MP4_SUFFIX else []

    if not root.is_dir():
        return []

    pattern = "**/*" if recursive else "*"
    files: list[Path] = []
    for path in root.glob(pattern):
        if path.is_file() and path.suffix.lower() in _MP4_SUFFIX:
            files.append(path)
    return sorted(files)


def _resolve_output_path(
    mp4: Path,
    input_root: Path,
    output_dir: Path | None,
) -> Path:
    if output_dir is None:
        return mp4.with_suffix(".mp3")
    try:
        rel = mp4.relative_to(input_root)
    except ValueError:
        rel = Path(mp4.name)
    return output_dir / rel.with_suffix(".mp3")


def _convert_one(mp4: Path, mp3: Path, *, overwrite: bool) -> None:
    if mp3.exists() and not overwrite:
        raise FileExistsError(f"已存在: {mp3}")

    ensure_dir(mp3.parent)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        str(mp4),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        str(mp3),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ffmpeg 失败").strip()
        raise RuntimeError(err[:500])


def mp4_to_mp3_batch(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    recursive: bool = False,
    overwrite: bool = False,
) -> JobResult:
    if not is_ffmpeg_available():
        return JobResult(
            ok=False,
            message="未找到 ffmpeg，请先安装（macOS: brew install ffmpeg）",
            errors=["ffmpeg 不在 PATH 中"],
        )

    root = Path(str(input_path).strip()).expanduser()
    if not root.exists():
        return JobResult(ok=False, message=f"路径不存在: {root}", errors=[str(root)])

    input_root = root if root.is_dir() else root.parent
    out_root = Path(output_dir).expanduser().resolve() if output_dir else None
    if out_root is not None:
        ensure_dir(out_root)

    files = _collect_mp4_files(root, recursive=recursive)
    if not files:
        return JobResult(
            ok=False,
            message="未找到 MP4 文件",
            errors=[f"在 {root} 下未匹配到 .mp4 / .m4v / .mov"],
        )

    processed = 0
    skipped = 0
    errors: list[str] = []
    details: list[str] = []
    outputs: list[Path] = []

    for mp4 in files:
        mp3 = _resolve_output_path(mp4, input_root, out_root)
        try:
            _convert_one(mp4, mp3, overwrite=overwrite)
            processed += 1
            outputs.append(mp3)
            details.append(f"✓ {mp4.name} → {mp3}")
        except FileExistsError:
            skipped += 1
            details.append(f"跳过（已存在）: {mp3}")
        except Exception as e:
            errors.append(f"{mp4.name}: {e}")

    ok = processed > 0 and not errors
    if processed and errors:
        ok = True
        message = f"完成 {processed} 个，跳过 {skipped} 个，失败 {len(errors)} 个"
    elif processed:
        message = f"已转换 {processed} 个 MP3" + (f"，跳过 {skipped} 个" if skipped else "")
    elif skipped and not errors:
        message = f"全部跳过（共 {skipped} 个，目标 MP3 已存在）"
        ok = True
    else:
        message = "转换失败"
        ok = False

    return JobResult(
        ok=ok,
        message=message,
        processed=processed,
        skipped=skipped,
        errors=errors,
        details=details,
        outputs=outputs,
    )
