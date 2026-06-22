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
from img_tools.to_ico import ToIcoOptions, convert_images_to_ico
from img_tools.compress import CompressOptions, compress_images, parse_max_bytes
from img_tools.format_convert import FormatConvertOptions, convert_images_format
from img_tools.crop_2k import crop_2k_png_recursive
from img_tools.filter_2k import filter_2k_images
from img_tools.rename import batch_rename_numbered, rename_sequential
from img_tools.rename_folders import SubfolderRenameOptions, rename_subfolders
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
from img_tools.tagger import WD14TagOptions, tag_images_wd14
from img_tools.lora_train import list_presets, load_preset_config, run_lora_train
from img_tools.lora_pipeline import LoraPipelineOptions, run_lora_pipeline
from img_tools.workflow import ResizeMode
from img_tools.caption import (
    CaptionCleanOptions,
    clean_captions_in_dir,
    get_tag_undesired_for_preset,
    get_trigger_for_preset,
    list_presets as list_caption_presets,
    load_preset as load_caption_preset,
)

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


class ToIcoRequest(BaseModel):
    input_dir: str
    output_dir: str | None = None
    sizes: str = "16,32,48,64,128,256"
    max_canvas: int = Field(256, ge=16, le=512)
    recursive: bool = False


class CompressRequest(BaseModel):
    input_dir: str
    output_dir: str | None = None
    max_size: float = Field(500, gt=0)
    size_unit: Literal["kb", "mb"] = "kb"
    output_format: Literal["auto", "jpeg", "webp", "png"] = "auto"
    recursive: bool = True
    in_place: bool = True


class FormatConvertRequest(BaseModel):
    input_dir: str
    output_dir: str | None = None
    target_format: Literal["png", "jpeg", "webp", "bmp", "gif", "tiff"] = "png"
    quality: int = Field(90, ge=1, le=100)
    recursive: bool = True
    in_place: bool = True
    skip_same_format: bool = False


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


class SubfolderRenameRequest(BaseModel):
    root_dir: str
    prefix: str = "10_"
    remove_spaces: bool = True
    recursive: bool = False
    dry_run: bool = True


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


class AutoTagRequest(BaseModel):
    image_dir: str
    repo_id: str = "SmilingWolf/wd-vit-tagger-v3"
    batch_size: int = Field(4, ge=1, le=32)
    general_threshold: float = Field(0.35, ge=0.0, le=1.0)
    character_threshold: float = Field(0.1, ge=0.0, le=1.0)
    trigger_word: str = ""
    undesired_tags: str = ""
    caption_preset: str = "default"
    auto_clean: bool = True
    clean_preset: str = ""
    recursive: bool = False
    remove_underscore: bool = False
    append_tags: bool = False


class CaptionCleanRequest(BaseModel):
    target_dir: str
    preset: str = "default"
    recursive: bool = False
    dry_run: bool = False
    trigger_word: str = ""
    strip_tags: str = ""
    ensure_tags: str = ""


def _resolve_tag_options(body: AutoTagRequest) -> WD14TagOptions:
    """合并 Caption 预设中的打标排除项（方案 3）。"""
    preset_id = body.caption_preset or "default"
    preset_undesired = get_tag_undesired_for_preset(preset_id)
    preset_trigger = get_trigger_for_preset(preset_id)

    undesired = body.undesired_tags.strip()
    if not undesired:
        undesired = preset_undesired
    elif preset_undesired:
        merged = {t.strip() for t in (undesired + ", " + preset_undesired).split(",") if t.strip()}
        undesired = ", ".join(sorted(merged))

    trigger = body.trigger_word.strip() or preset_trigger

    return WD14TagOptions(
        repo_id=body.repo_id,
        batch_size=body.batch_size,
        general_threshold=body.general_threshold,
        character_threshold=body.character_threshold,
        always_first_tags=trigger,
        undesired_tags=undesired,
        recursive=body.recursive,
        remove_underscore=body.remove_underscore,
        append_tags=body.append_tags,
    )


def _merge_job_results(tag: JobResult, clean: JobResult) -> JobResult:
    return JobResult(
        ok=tag.ok and clean.ok,
        message=f"{tag.message} → {clean.message}",
        processed=tag.processed + clean.processed,
        skipped=tag.skipped + clean.skipped,
        errors=[*tag.errors, *clean.errors],
        details=[*tag.details, *clean.details],
        outputs=[*tag.outputs, *clean.outputs],
    )


class LoraTrainRequest(BaseModel):
    preset: str = "morgana_star_nemesis"
    train_data_dir: str | None = None
    pretrained_model_name_or_path: str | None = None
    output_name: str | None = None
    output_dir: str | None = None
    max_train_epochs: int | None = Field(None, ge=1)
    train_batch_size: int | None = Field(None, ge=1)
    save_every_n_epochs: int | None = Field(None, ge=1)
    resolution_width: int | None = Field(None, ge=256)
    resolution_height: int | None = Field(None, ge=256)
    network_dim: int | None = Field(None, ge=1)
    network_alpha: int | None = Field(None, ge=1)
    unet_lr: float | None = Field(None, gt=0)
    keep_tokens: int | None = Field(None, ge=0)
    bucket_no_upscale: bool | None = None
    full_bf16: bool | None = None


class LoraPipelineRequest(BaseModel):
    """LoRA 角色训练完整流水线（8 步）。"""

    character_root: str
    repeat_count: int = Field(10, ge=1, le=999)
    resize_mode: Literal["area_64", "fixed_canvas"] = "area_64"
    target_width: int = Field(1024, ge=1)
    target_height: int = Field(1024, ge=1)
    rename_prefix: str = ""
    rename_digits: int = Field(4, ge=1, le=8)
    caption_preset: str = "default"
    trigger_word: str = ""
    extra_undesired_tags: str = ""
    tag_general_threshold: float = Field(0.35, ge=0.0, le=1.0)
    tag_character_threshold: float = Field(0.1, ge=0.0, le=1.0)
    lora_preset: str = "morgana_star_nemesis"
    pretrained_model_name_or_path: str | None = None
    output_name: str | None = None
    output_dir: str | None = None
    max_train_epochs: int | None = Field(None, ge=1)
    train_batch_size: int | None = Field(None, ge=1)
    save_every_n_epochs: int | None = Field(None, ge=1)
    resolution_width: int | None = Field(None, ge=256)
    resolution_height: int | None = Field(None, ge=256)
    network_dim: int | None = Field(None, ge=1)
    network_alpha: int | None = Field(None, ge=1)
    unet_lr: float | None = Field(None, gt=0)
    keep_tokens: int | None = Field(None, ge=0)
    bucket_no_upscale: bool | None = None
    full_bf16: bool | None = None


def _lora_train_overrides(body: LoraTrainRequest) -> dict[str, Any]:
    """将 Hub 表单字段转为 Kohya 配置覆盖项。"""
    overrides: dict[str, Any] = {}
    direct = (
        "train_data_dir",
        "pretrained_model_name_or_path",
        "output_name",
        "output_dir",
        "max_train_epochs",
        "train_batch_size",
        "save_every_n_epochs",
        "network_dim",
        "network_alpha",
        "keep_tokens",
        "bucket_no_upscale",
        "full_bf16",
    )
    for key in direct:
        val = getattr(body, key)
        if val is not None and val != "":
            overrides[key] = val

    if body.resolution_width and body.resolution_height:
        overrides["resolution"] = f"{body.resolution_width},{body.resolution_height}"

    if body.unet_lr is not None:
        overrides["unet_lr"] = body.unet_lr
        overrides["learning_rate"] = body.unet_lr

    return overrides


def _pipeline_lora_overrides(body: LoraPipelineRequest) -> dict[str, Any]:
    """流水线训练步覆盖项（train_data_dir 由 runner 强制设为 output/）。"""
    fake = LoraTrainRequest(
        preset=body.lora_preset,
        pretrained_model_name_or_path=body.pretrained_model_name_or_path,
        output_name=body.output_name,
        output_dir=body.output_dir,
        max_train_epochs=body.max_train_epochs,
        train_batch_size=body.train_batch_size,
        save_every_n_epochs=body.save_every_n_epochs,
        resolution_width=body.resolution_width,
        resolution_height=body.resolution_height,
        network_dim=body.network_dim,
        network_alpha=body.network_alpha,
        unet_lr=body.unet_lr,
        keep_tokens=body.keep_tokens,
        bucket_no_upscale=body.bucket_no_upscale,
        full_bf16=body.full_bf16,
    )
    return _lora_train_overrides(fake)


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

    onnx_ok = False
    try:
        import onnxruntime  # noqa: F401

        onnx_ok = True
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
            "onnxruntime": onnx_ok,
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


@app.post("/api/jobs/to-ico")
def job_to_ico(body: ToIcoRequest) -> dict:
    def run() -> JobResult:
        return convert_images_to_ico(
            body.input_dir,
            body.output_dir,
            options=ToIcoOptions(
                max_canvas=body.max_canvas,
                recursive=body.recursive,
            ),
            sizes=body.sizes,
        )

    job_id = job_manager.submit("to-ico", run)
    return {"job_id": job_id}


@app.post("/api/jobs/compress")
def job_compress(body: CompressRequest) -> dict:
    opts = CompressOptions(
        max_bytes=parse_max_bytes(body.max_size, body.size_unit),
        output_format=body.output_format,
        recursive=body.recursive,
        in_place=body.in_place,
    )

    def run() -> JobResult:
        return compress_images(body.input_dir, body.output_dir, options=opts)

    job_id = job_manager.submit("compress", run)
    return {"job_id": job_id}


@app.post("/api/jobs/format-convert")
def job_format_convert(body: FormatConvertRequest) -> dict:
    opts = FormatConvertOptions(
        target_format=body.target_format,
        quality=body.quality,
        recursive=body.recursive,
        in_place=body.in_place,
        skip_same_format=body.skip_same_format,
    )

    def run() -> JobResult:
        return convert_images_format(body.input_dir, body.output_dir, options=opts)

    job_id = job_manager.submit("format-convert", run)
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


@app.post("/api/jobs/rename-subfolders")
def job_rename_subfolders(body: SubfolderRenameRequest) -> dict:
    opts = SubfolderRenameOptions(
        prefix=body.prefix,
        remove_spaces=body.remove_spaces,
        recursive=body.recursive,
        dry_run=body.dry_run,
    )

    def run() -> JobResult:
        return rename_subfolders(body.root_dir, options=opts)

    job_id = job_manager.submit("rename-subfolders", run)
    return {"job_id": job_id}


@app.post("/api/jobs/lora-pipeline")
def job_lora_pipeline(body: LoraPipelineRequest) -> dict:
    lora_overrides = _pipeline_lora_overrides(body)
    pipe_opts = LoraPipelineOptions(
        character_root=body.character_root,
        repeat_count=body.repeat_count,
        resize_mode=ResizeMode(body.resize_mode),
        target_width=body.target_width,
        target_height=body.target_height,
        rename_prefix=body.rename_prefix,
        rename_digits=body.rename_digits,
        caption_preset=body.caption_preset,
        trigger_word=body.trigger_word,
        extra_undesired_tags=body.extra_undesired_tags,
        tag_general_threshold=body.tag_general_threshold,
        tag_character_threshold=body.tag_character_threshold,
        lora_preset=body.lora_preset,
        lora_overrides=lora_overrides,
    )

    def build_run(job_id: str):
        def on_progress(prog: dict, line: str) -> None:
            job_manager.update_live(job_id, progress=prog, log_line=line)

        def run() -> JobResult:
            return run_lora_pipeline(pipe_opts, progress_callback=on_progress)

        return run

    job_id = job_manager.submit_builder("lora-pipeline", build_run)
    return {"job_id": job_id}


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


@app.post("/api/jobs/auto-tag")
def job_auto_tag(body: AutoTagRequest) -> dict:
    opts = _resolve_tag_options(body)
    clean_preset = body.clean_preset.strip() or body.caption_preset or "default"

    def run() -> JobResult:
        tag_result = tag_images_wd14(body.image_dir, opts)
        if not body.auto_clean or not tag_result.ok:
            return tag_result
        clean_opts = CaptionCleanOptions(
            preset=clean_preset,
            recursive=body.recursive,
            dry_run=False,
            trigger_word=opts.always_first_tags or None,
        )
        clean_result = clean_captions_in_dir(body.image_dir, clean_opts)
        return _merge_job_results(tag_result, clean_result)

    job_id = job_manager.submit("auto-tag", run)
    return {"job_id": job_id}


@app.get("/api/caption/presets")
def api_caption_presets() -> dict:
    return {"presets": list_caption_presets()}


@app.get("/api/caption/presets/{preset_id}")
def api_caption_preset_detail(preset_id: str) -> dict:
    try:
        config = load_caption_preset(preset_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Caption 预设不存在")
    return {
        "preset": preset_id,
        "config": config,
        "tag_undesired": get_tag_undesired_for_preset(preset_id),
        "trigger_word": get_trigger_for_preset(preset_id),
    }


@app.post("/api/jobs/caption-clean")
def job_caption_clean(body: CaptionCleanRequest) -> dict:
    opts = CaptionCleanOptions(
        preset=body.preset,
        recursive=body.recursive,
        dry_run=body.dry_run,
        trigger_word=body.trigger_word or None,
        strip_tags=body.strip_tags or None,
        ensure_tags=body.ensure_tags or None,
    )

    def run() -> JobResult:
        return clean_captions_in_dir(body.target_dir, opts)

    job_id = job_manager.submit("caption-clean", run)
    return {"job_id": job_id}


@app.get("/api/lora/presets")
def api_lora_presets() -> dict:
    return {"presets": list_presets()}


@app.get("/api/lora/presets/{preset_id}")
def api_lora_preset_detail(preset_id: str) -> dict:
    try:
        config = load_preset_config(preset_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="预设不存在")
    return {"preset": preset_id, "config": config}


@app.post("/api/jobs/lora-train")
def job_lora_train(body: LoraTrainRequest) -> dict:
    overrides = _lora_train_overrides(body)

    def build_run(job_id: str):
        def on_progress(prog: dict, line: str) -> None:
            job_manager.update_live(job_id, progress=prog, log_line=line)

        def run() -> JobResult:
            return run_lora_train(body.preset, overrides=overrides, progress_callback=on_progress)

        return run

    job_id = job_manager.submit_builder("lora-train", build_run)
    return {"job_id": job_id}


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="前端未找到")
    return FileResponse(index_path)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
