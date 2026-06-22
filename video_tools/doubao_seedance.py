"""火山方舟 Seedance 视频生成 API 客户端。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from img_tools.common import JobResult, ensure_dir
from video_tools.config import get_api_key
from video_tools.duration import detect_generation_mode, validate_duration
from video_tools.media_resolve import resolve_reference_url

BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-1-5-pro-251215"
DEFAULT_RATIO = "adaptive"
DEFAULT_RESOLUTION = "480p"

VALID_RATIOS = frozenset({"16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"})
VALID_RESOLUTIONS = frozenset({"480p", "720p", "1080p"})

ReferenceType = Literal["image_url", "video_url", "audio_url"]
ReferenceRole = Literal[
    "reference_image",
    "reference_video",
    "reference_audio",
    "first_frame",
    "last_frame",
]


@dataclass
class MediaReference:
    type: ReferenceType
    url: str
    role: ReferenceRole | str | None = None


@dataclass
class SeedanceRequest:
    prompt: str
    references: list[MediaReference] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    ratio: str = DEFAULT_RATIO
    resolution: str = DEFAULT_RESOLUTION
    duration: int = 5
    generate_audio: bool = True
    watermark: bool = False


class DoubaoApiError(Exception):
    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _api_request(
    method: str,
    path: str,
    *,
    api_key: str,
    body: dict | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise DoubaoApiError(
            f"API 请求失败 HTTP {e.code}: {err_body[:500]}",
            status=e.code,
            body=err_body,
        ) from e
    except urllib.error.URLError as e:
        raise DoubaoApiError(f"网络错误: {e.reason}") from e


def build_content(prompt: str, references: list[MediaReference]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    ref_index = 0
    for ref in references:
        if not ref.url.strip():
            continue
        ref_index += 1
        label = f"参考素材 #{ref_index}"
        try:
            resolved = resolve_reference_url(ref.url, ref.type, label=label)
        except ValueError as e:
            raise ValueError(str(e)) from e
        if not resolved.startswith(("http://", "https://", "data:")):
            raise ValueError(
                f"{label} 无法用于 API（{ref.url.strip()}）。"
                "请填写可访问的 https 链接，或存在的本机绝对路径。"
            )
        item: dict[str, Any] = {"type": ref.type}
        if ref.type == "image_url":
            item["image_url"] = {"url": resolved}
        elif ref.type == "video_url":
            item["video_url"] = {"url": resolved}
        elif ref.type == "audio_url":
            item["audio_url"] = {"url": resolved}
        if ref.role:
            item["role"] = ref.role
        content.append(item)
    return content


def normalize_ratio(ratio: str) -> str:
    """校验并规范化画幅比例；adaptive 表示由模型根据参考图/提示词自动选择最接近的标准比例。"""
    raw = (ratio or DEFAULT_RATIO).strip()
    aliases = {"auto", "智能", "跟随参考图", "自适应"}
    if raw.lower() in aliases or raw == "跟随参考图":
        return "adaptive"
    if raw not in VALID_RATIOS:
        allowed = "、".join(sorted(VALID_RATIOS))
        raise ValueError(f"不支持的画幅比例「{raw}」，可选: {allowed}")
    return raw


def normalize_resolution(resolution: str) -> str:
    """校验并规范化输出分辨率。"""
    raw = (resolution or DEFAULT_RESOLUTION).strip().lower()
    if raw not in VALID_RESOLUTIONS:
        allowed = "、".join(sorted(VALID_RESOLUTIONS))
        raise ValueError(f"不支持的分辨率「{raw}」，可选: {allowed}")
    return raw


def build_task_payload(req: SeedanceRequest) -> dict[str, Any]:
    mode = detect_generation_mode(req.references)
    duration = validate_duration(req.duration, mode)
    ratio = normalize_ratio(req.ratio)
    resolution = normalize_resolution(req.resolution)
    return {
        "model": req.model,
        "content": build_content(req.prompt, req.references),
        "generate_audio": req.generate_audio,
        "ratio": ratio,
        "resolution": resolution,
        "duration": duration,
        "watermark": req.watermark,
    }


def create_generation_task(
    payload: dict[str, Any],
    *,
    api_key: str | None = None,
) -> dict[str, Any]:
    key = api_key or get_api_key()
    if not key:
        raise DoubaoApiError("未配置 API Key，请在项目根目录 .env 中设置 ARK_API_KEY")
    return _api_request("POST", "/contents/generations/tasks", api_key=key, body=payload)


def get_generation_task(task_id: str, *, api_key: str | None = None) -> dict[str, Any]:
    key = api_key or get_api_key()
    if not key:
        raise DoubaoApiError("未配置 API Key")
    return _api_request("GET", f"/contents/generations/tasks/{task_id}", api_key=key)


def extract_task_id(response: dict[str, Any]) -> str:
    task_id = response.get("id") or response.get("task_id")
    if not task_id:
        raise DoubaoApiError(f"响应中无任务 ID: {response}")
    return str(task_id)


def extract_video_url(task_data: dict[str, Any]) -> str | None:
    content = task_data.get("content")
    if isinstance(content, dict):
        url = content.get("video_url")
        if url:
            return str(url)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("video_url"):
                v = item["video_url"]
                if isinstance(v, dict) and v.get("url"):
                    return str(v["url"])
                if isinstance(v, str):
                    return v
    return None


def resolve_video_output_path(
    output_path: str | Path,
    *,
    task_id: str | None = None,
) -> Path:
    """将用户输入解析为可写入的视频文件路径（目录则自动生成文件名）。"""
    raw = str(output_path).strip()
    path = Path(raw).expanduser()
    name_base = (task_id or f"{int(time.time())}").replace("/", "-")
    default_name = f"seedance_{name_base}.mp4"

    if raw.endswith(("/", "\\")) or path.is_dir():
        return path / default_name

    if not path.suffix or path.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
        return path.with_suffix(".mp4")

    return path


def download_video(url: str, output_path: str | Path, *, task_id: str | None = None) -> Path:
    dest = resolve_video_output_path(output_path, task_id=task_id)
    ensure_dir(dest.parent)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=300) as resp:
        dest.write_bytes(resp.read())
    return dest


def format_task_error(err: Any) -> str:
    """将方舟任务 error 字段转为可读中文说明。"""
    if isinstance(err, dict):
        code = str(err.get("code", ""))
        msg = str(err.get("message", ""))
        hints: dict[str, str] = {
            "OutputVideoSensitiveContentDetected.PolicyViolation": (
                "生成结果被判定可能涉及版权或平台限制（如知名 IP、影视角色、品牌 logo、"
                "可识别公众人物等），任务已终止。请更换参考图、弱化具体作品/人物名称，"
                "改写提示词后重试。"
            ),
            "InputImageSensitiveContentDetected": (
                "参考图/输入素材未通过内容审核。请更换图片后重试。"
            ),
            "InputTextSensitiveContentDetected": (
                "提示词未通过内容审核。请修改描述后重试。"
            ),
        }
        for key, hint in hints.items():
            if key in code:
                detail = f"\n原始说明: {msg}" if msg else ""
                return f"{hint}{detail}\n错误码: {code}"
        if code and msg:
            return f"{msg}\n错误码: {code}"
        return msg or str(err)
    return str(err)


def poll_generation_task(
    task_id: str,
    *,
    api_key: str | None = None,
    poll_interval: float = 10.0,
    max_wait: float = 1800.0,
    on_status: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """轮询直到 succeeded / failed / cancelled / expired。"""
    key = api_key or get_api_key()
    if not key:
        raise DoubaoApiError("未配置 API Key")

    terminal = {"succeeded", "failed", "cancelled", "expired"}
    waited = 0.0
    while waited <= max_wait:
        data = get_generation_task(task_id, api_key=key)
        status = str(data.get("status", "unknown"))
        if on_status:
            on_status(status, data)
        if status in terminal:
            return data
        time.sleep(poll_interval)
        waited += poll_interval

    raise DoubaoApiError(f"任务 {task_id} 轮询超时（>{max_wait}s）")


def run_seedance_generation(
    req: SeedanceRequest,
    *,
    output_path: str | Path | None = None,
    api_key: str | None = None,
    poll_interval: float = 10.0,
    on_progress: Callable[[str], None] | None = None,
) -> JobResult:
    """创建任务、轮询、可选下载，返回 JobResult。"""

    def _progress(msg: str) -> None:
        details.append(msg)
        if on_progress:
            on_progress(msg)

    details: list[str] = []
    try:
        ratio = normalize_ratio(req.ratio)
        resolution = normalize_resolution(req.resolution)
        _progress(f"画幅比例: {ratio}" + ("（按参考图/提示词自动匹配）" if ratio == "adaptive" else ""))
        _progress(f"输出分辨率: {resolution}")
        payload = build_task_payload(req)
        _progress("正在向火山方舟提交视频任务…")
        create_resp = create_generation_task(payload, api_key=api_key)
        task_id = extract_task_id(create_resp)
        _progress(f"方舟任务已创建: {task_id}")
        details.append(f"模型: {req.model}")
        details.append(f"分辨率: {resolution}")

        def _log_status(status: str, _data: dict) -> None:
            label = {
                "queued": "排队中",
                "running": "生成中",
                "succeeded": "已完成",
                "failed": "失败",
                "cancelled": "已取消",
                "expired": "已过期",
            }.get(status, status)
            _progress(f"云端状态: {label} ({status})")

        _progress(f"开始轮询（每 {int(poll_interval)} 秒查询一次，通常需 1–5 分钟）…")
        final = poll_generation_task(
            task_id,
            api_key=api_key,
            poll_interval=poll_interval,
            on_status=_log_status,
        )
        status = str(final.get("status", ""))

        if status != "succeeded":
            err = final.get("error") or final.get("message") or status
            friendly = format_task_error(err)
            return JobResult(
                ok=False,
                message=f"视频生成失败: {friendly.split(chr(10))[0]}",
                errors=[friendly],
                details=details,
            )

        video_url = extract_video_url(final)
        if not video_url:
            return JobResult(
                ok=False,
                message="任务成功但未返回 video_url",
                details=details,
                errors=[json.dumps(final, ensure_ascii=False)[:500]],
            )

        details.append(f"视频链接（24h 内有效）: {video_url}")

        if output_path:
            dest = resolve_video_output_path(output_path, task_id=task_id)
            if Path(output_path).expanduser().is_dir() or str(output_path).rstrip().endswith(("/", "\\")):
                _progress(f"保存路径为目录，将下载为: {dest.name}")
            _progress(f"正在下载视频到 {dest}…")
            try:
                saved = download_video(video_url, output_path, task_id=task_id)
                details.append(f"已下载到: {saved}")
                outputs: list[Path] = [saved]
            except OSError as e:
                return JobResult(
                    ok=True,
                    message="视频已生成，但保存到本地失败",
                    processed=1,
                    details=details,
                    errors=[f"下载失败: {e}（在线链接仍有效，请手动下载）"],
                )
        else:
            outputs = []

        _progress("全部完成")
        return JobResult(
            ok=True,
            message="视频生成成功",
            processed=1,
            details=details,
            outputs=outputs,
        )
    except ValueError as e:
        return JobResult(ok=False, message=str(e), errors=[str(e)], details=details)
    except DoubaoApiError as e:
        return JobResult(ok=False, message=str(e), errors=[str(e)], details=details)
    except Exception as e:
        return JobResult(ok=False, message=f"未知错误: {e}", errors=[str(e)], details=details)
