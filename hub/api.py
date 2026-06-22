"""FastAPI 路由：任务 API、目录浏览、静态资源。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from audio_tools.mp4_to_mp3 import is_ffmpeg_available, mp4_to_mp3_batch
from hub.browse import browse_directory, browse_media
from hub.config import HOST, PORT
from hub.jobs import job_manager
from img_tools.common import JobResult, register_heif_opener
from img_tools.convert import process_all
from img_tools.crop_2k import crop_2k_png_recursive
from img_tools.filter_2k import filter_2k_images
from img_tools.rename import batch_rename_numbered, rename_sequential
from img_tools.resize import resize_png_center_batch
from img_tools.workflow import RenameMode, ResizeMode, WorkflowRenameOptions, run_prepare_workflow
from video_tools.config import is_api_key_configured
from video_tools.doubao_seedance import (
    DEFAULT_MODEL,
    DEFAULT_RATIO,
    DEFAULT_RESOLUTION,
    MediaReference,
    SeedanceRequest,
    run_seedance_generation,
)
from video_tools.media_resolve import MAX_BYTES, guess_ref_type, validate_local_media

STATIC_DIR = Path(__file__).resolve().parent / "static"
STAGING_DIR = Path(__file__).resolve().parent / ".staging"

app = FastAPI(title="AITrainScripts Hub", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://{HOST}:{PORT}",
        f"http://localhost:{PORT}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request models ---


class ConvertRequest(BaseModel):
    target_path: str
    output_path: str
    base_width: int = Field(1024, ge=64)
    base_height: int = Field(1024, ge=64)
    recursive: bool = False
    rename_output: bool = True


class ResizeCanvasRequest(BaseModel):
    input_dir: str
    output_dir: str | None = None
    canvas_width: int = Field(1024, ge=1)
    canvas_height: int = Field(1024, ge=1)
    recursive: bool = False


class Crop2kRequest(BaseModel):
    input_root: str
    output_root: str


class Filter2kRequest(BaseModel):
    target_dir: str
    target_width: int = Field(2560, ge=1)
    target_height: int = Field(1440, ge=1)
    dry_run: bool = True


class RenameRequest(BaseModel):
    mode: Literal["numbered", "sequential"]
    folder_path: str
    dry_run: bool = True
    prefix: str = ""
    start_num: int = 1
    digits: int = 3
    start_index: int = 1
    sync_captions: bool = False


class Mp4ToMp3Request(BaseModel):
    input_path: str = Field(..., min_length=1)
    output_dir: str | None = None
    recursive: bool = False
    overwrite: bool = False


class VideoReferenceItem(BaseModel):
    type: Literal["image_url", "video_url", "audio_url"]
    url: str
    role: str | None = None


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    references: list[VideoReferenceItem] = Field(default_factory=list)
    model: str = DEFAULT_MODEL
    ratio: str = DEFAULT_RATIO
    resolution: str = DEFAULT_RESOLUTION
    duration: int = Field(5, ge=-1, le=15)
    generate_audio: bool = True
    watermark: bool = False
    output_path: str | None = None


class VideoBatchItem(BaseModel):
    """批量队列中的单条：通常仅一张参考图对应一个视频。"""

    url: str = Field(..., min_length=1)
    label: str | None = None
    role: str = "reference_image"


class VideoBatchRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    items: list[VideoBatchItem] = Field(..., min_length=1, max_length=30)
    model: str = DEFAULT_MODEL
    ratio: str = DEFAULT_RATIO
    resolution: str = DEFAULT_RESOLUTION
    duration: int = Field(5, ge=-1, le=15)
    generate_audio: bool = True
    watermark: bool = False
    output_dir: str | None = None
    output_path: str | None = None


class WorkflowRequest(BaseModel):
    source_dir: str
    output_dir: str
    target_width: int = Field(1024, ge=1)
    target_height: int = Field(1024, ge=1)
    resize_mode: Literal["area_64", "fixed_canvas"] = "area_64"
    recursive: bool = False
    rename_mode: Literal["numbered", "sequential", "none"] = "numbered"
    prefix: str = ""
    start_num: int = Field(1, ge=0)
    digits: int = Field(4, ge=1, le=8)
    start_index: int = Field(1, ge=0)
    sync_captions: bool = True


# --- Routes ---


@app.get("/api/health")
def health() -> dict[str, Any]:
    pillow_ok = False
    try:
        from PIL import Image  # noqa: F401

        pillow_ok = True
    except ImportError:
        pass

    heif_ok = register_heif_opener()
    natsort_ok = False
    try:
        import natsort  # noqa: F401

        natsort_ok = True
    except ImportError:
        pass

    return {
        "status": "ok",
        "dependencies": {
            "pillow": pillow_ok,
            "pillow_heif": heif_ok,
            "natsort": natsort_ok,
            "ffmpeg": is_ffmpeg_available(),
            "ark_api_key": is_api_key_configured(),
        },
    }


@app.get("/api/browse")
def api_browse(path: str | None = Query(None)) -> dict:
    return browse_directory(path)


@app.get("/api/browse/media")
def api_browse_media(path: str | None = Query(None)) -> dict:
    return browse_media(path)


@app.get("/api/video/check-media")
def check_video_media(
    path: str = Query(..., min_length=1),
    ref_type: str = Query("image_url"),
) -> dict[str, Any]:
    """校验用户填写的本机媒体路径是否存在、可读。"""
    if ref_type not in MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"不支持的素材类型: {ref_type}")
    try:
        return validate_local_media(path, ref_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/video/stage-media")
async def stage_video_media(
    file: UploadFile = File(...),
    ref_type: str = Form("image_url"),
) -> dict[str, Any]:
    """浏览器上传的参考素材暂存到本机，提交任务时再转为 data URI 发给方舟 API。"""
    if ref_type not in MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"不支持的素材类型: {ref_type}")

    original = Path(file.filename or "upload").name
    suffix = Path(original).suffix.lower() or ".bin"
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    dest = STAGING_DIR / f"{uuid.uuid4().hex}{suffix}"

    max_bytes = MAX_BYTES[ref_type]
    written = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"文件过大，{ref_type} 上限 {max_bytes // (1024 * 1024)} MB",
                    )
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise

    detected = guess_ref_type(dest)
    return {
        "path": str(dest.resolve()),
        "name": original,
        "size": written,
        "detected_type": detected,
    }


def _safe_batch_label(name: str | None, index: int) -> str:
    stem = Path(name).stem if name else f"item-{index + 1}"
    safe = re.sub(r"[^\w\-.]+", "_", stem, flags=re.UNICODE).strip("._")
    return safe[:60] or f"item-{index + 1}"


def _resolve_batch_output_path(
    *,
    output_dir: str | None,
    output_path: str | None,
    label: str,
    index: int,
) -> str | None:
    if output_dir and output_dir.strip():
        return str(Path(output_dir.strip()).expanduser() / f"seedance_{label}.mp4")
    if output_path and output_path.strip():
        raw = output_path.strip()
        path = Path(raw).expanduser()
        if path.is_dir() or raw.endswith(("/", "\\")):
            return str(path / f"seedance_{label}.mp4")
    return None


def _submit_video_job(
    *,
    prompt: str,
    references: list[MediaReference],
    model: str,
    ratio: str,
    resolution: str,
    duration: int,
    generate_audio: bool,
    watermark: bool,
    output_path: str | None,
    label: str | None = None,
    batch_id: str | None = None,
) -> str:
    req = SeedanceRequest(
        prompt=prompt,
        references=references,
        model=model,
        ratio=ratio,
        resolution=resolution,
        duration=duration,
        generate_audio=generate_audio,
        watermark=watermark,
    )

    def run(report) -> JobResult:
        return run_seedance_generation(req, output_path=output_path, on_progress=report)

    return job_manager.submit(
        "video-generate",
        run,
        with_progress=True,
        label=label,
        batch_id=batch_id,
    )


@app.get("/api/jobs")
def list_jobs(
    job_type: str | None = Query(None),
    batch_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    records = job_manager.list_jobs(job_type=job_type, batch_id=batch_id, limit=limit)
    return {"jobs": [job_manager.to_dict(r) for r in records]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    record = job_manager.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job_manager.to_dict(record)


@app.post("/api/jobs/convert")
def job_convert(body: ConvertRequest) -> dict:
    target_area = body.base_width * body.base_height

    def run() -> JobResult:
        return process_all(
            body.target_path,
            body.output_path,
            target_area,
            body.recursive,
            rename_output=body.rename_output,
        )

    job_id = job_manager.submit("convert", run)
    return {"job_id": job_id}


@app.post("/api/jobs/resize-canvas")
def job_resize_canvas(body: ResizeCanvasRequest) -> dict:
    def run() -> JobResult:
        return resize_png_center_batch(
            body.input_dir,
            body.output_dir,
            canvas_width=body.canvas_width,
            canvas_height=body.canvas_height,
            recursive=body.recursive,
        )

    job_id = job_manager.submit("resize-canvas", run)
    return {"job_id": job_id}


@app.post("/api/jobs/resize-1024")
def job_resize_1024_compat(body: ResizeCanvasRequest) -> dict:
    """兼容旧路径。"""
    return job_resize_canvas(body)


@app.post("/api/jobs/crop-2k")
def job_crop_2k(body: Crop2kRequest) -> dict:
    def run() -> JobResult:
        return crop_2k_png_recursive(body.input_root, body.output_root)

    job_id = job_manager.submit("crop-2k", run)
    return {"job_id": job_id}


@app.post("/api/jobs/filter-2k")
def job_filter_2k(body: Filter2kRequest) -> dict:
    def run() -> JobResult:
        return filter_2k_images(
            body.target_dir,
            target_width=body.target_width,
            target_height=body.target_height,
            dry_run=body.dry_run,
        )

    job_id = job_manager.submit("filter-2k", run)
    return {"job_id": job_id}


@app.post("/api/jobs/rename")
def job_rename(body: RenameRequest) -> dict:
    def run() -> JobResult:
        if body.mode == "numbered":
            return batch_rename_numbered(
                body.folder_path,
                prefix=body.prefix,
                start_num=body.start_num,
                digits=body.digits,
                dry_run=body.dry_run,
                sync_captions=body.sync_captions,
            )
        return rename_sequential(
            body.folder_path,
            body.start_index,
            dry_run=body.dry_run,
            sync_captions=body.sync_captions,
        )

    job_id = job_manager.submit("rename", run)
    return {"job_id": job_id}


@app.post("/api/jobs/mp4-to-mp3")
def job_mp4_to_mp3(body: Mp4ToMp3Request) -> dict:
    def run() -> JobResult:
        return mp4_to_mp3_batch(
            body.input_path,
            body.output_dir,
            recursive=body.recursive,
            overwrite=body.overwrite,
        )

    job_id = job_manager.submit("mp4-to-mp3", run)
    return {"job_id": job_id}


@app.post("/api/jobs/video-generate")
def job_video_generate(body: VideoGenerateRequest) -> dict:
    if not is_api_key_configured():
        raise HTTPException(
            status_code=400,
            detail="未配置 ARK_API_KEY。请在项目根目录创建 .env 并填入密钥（参考 .env.example）",
        )

    refs = [
        MediaReference(type=r.type, url=r.url, role=r.role) for r in body.references if r.url.strip()
    ]
    job_id = _submit_video_job(
        prompt=body.prompt,
        references=refs,
        model=body.model,
        ratio=body.ratio,
        resolution=body.resolution,
        duration=body.duration,
        generate_audio=body.generate_audio,
        watermark=body.watermark,
        output_path=body.output_path,
    )
    return {"job_id": job_id}


@app.post("/api/jobs/video-generate-batch")
def job_video_generate_batch(body: VideoBatchRequest) -> dict[str, Any]:
    if not is_api_key_configured():
        raise HTTPException(
            status_code=400,
            detail="未配置 ARK_API_KEY。请在项目根目录创建 .env 并填入密钥（参考 .env.example）",
        )

    batch_id = uuid.uuid4().hex[:10]
    jobs: list[dict[str, str]] = []

    for index, item in enumerate(body.items):
        label = _safe_batch_label(item.label or item.url, index)
        output_path = _resolve_batch_output_path(
            output_dir=body.output_dir,
            output_path=body.output_path,
            label=label,
            index=index,
        )
        refs = [
            MediaReference(
                type="image_url",
                url=item.url.strip(),
                role=item.role or "reference_image",
            )
        ]
        job_id = _submit_video_job(
            prompt=body.prompt,
            references=refs,
            model=body.model,
            ratio=body.ratio,
            resolution=body.resolution,
            duration=body.duration,
            generate_audio=body.generate_audio,
            watermark=body.watermark,
            output_path=output_path,
            label=label,
            batch_id=batch_id,
        )
        jobs.append({"job_id": job_id, "label": label, "output_path": output_path or ""})

    return {
        "batch_id": batch_id,
        "total": len(jobs),
        "jobs": jobs,
        "message": f"已提交 {len(jobs)} 个视频任务，后台并行处理（最多 4 路同时运行）",
    }


@app.post("/api/jobs/workflow")
def job_workflow(body: WorkflowRequest) -> dict:
    rename = WorkflowRenameOptions(
        mode=RenameMode(body.rename_mode),
        prefix=body.prefix,
        start_num=body.start_num,
        digits=body.digits,
        start_index=body.start_index,
        sync_captions=body.sync_captions,
    )

    def run() -> JobResult:
        return run_prepare_workflow(
            body.source_dir,
            body.output_dir,
            body.target_width,
            body.target_height,
            ResizeMode(body.resize_mode),
            recursive=body.recursive,
            rename=rename,
        )

    job_id = job_manager.submit("workflow", run)
    return {"job_id": job_id}


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="前端未找到")
    return FileResponse(index_path)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
