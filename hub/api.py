"""FastAPI 路由：任务 API、目录浏览、静态资源。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from hub.browse import browse_directory
from hub.config import HOST, PORT
from hub.jobs import job_manager
from img_tools.common import JobResult, register_heif_opener
from img_tools.convert import process_all
from img_tools.crop_2k import crop_2k_png_recursive
from img_tools.filter_2k import filter_2k_images
from img_tools.rename import batch_rename_numbered, rename_sequential
from img_tools.resize import resize_png_center_batch
from img_tools.workflow import RenameMode, ResizeMode, WorkflowRenameOptions, run_prepare_workflow

STATIC_DIR = Path(__file__).resolve().parent / "static"

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
        },
    }


@app.get("/api/browse")
def api_browse(path: str | None = Query(None)) -> dict:
    return browse_directory(path)


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
