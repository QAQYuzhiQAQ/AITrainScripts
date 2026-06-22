"""
WD14 自动打标（Danbooru 风格 tag → 同名 .txt）

实现参考 lora-scripts v1.12.0:
  - scripts/stable/finetune/tag_images_by_wd14_tagger.py
  - mikazuki/tagger/interrogator.py
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from huggingface_hub import hf_hub_download
from PIL import Image

from img_tools.common import COMMON_IMAGE_EXTENSIONS, JobResult

logger = logging.getLogger(__name__)

IMAGE_SIZE = 448
CSV_FILE = "selected_tags.csv"
DEFAULT_REPO = "SmilingWolf/wd-vit-tagger-v3"

# 已从 lora-scripts 本地复制的模型（无需联网下载）
BUNDLED_REPO_IDS = frozenset({
    "SmilingWolf/wd-vit-tagger-v3",
})

WD14_MODELS: dict[str, str] = {
    "wd-vit-v3 (推荐·已内置)": "SmilingWolf/wd-vit-tagger-v3",
    "wd-v1-4-swinv2-v2": "SmilingWolf/wd-v1-4-swinv2-tagger-v2",
    "wd-v1-4-convnextv2-v2": "SmilingWolf/wd-v1-4-convnextv2-tagger-v2",
    "wd-v1-4-convnext-v2": "SmilingWolf/wd-v1-4-convnext-tagger-v2",
    "wd-v1-4-vit-v2": "SmilingWolf/wd-v1-4-vit-tagger-v2",
    "wd-v1-4-moat-v2": "SmilingWolf/wd-v1-4-moat-tagger-v2",
    "wd-convnext-v3": "SmilingWolf/wd-convnext-tagger-v3",
    "wd-swinv2-v3": "SmilingWolf/wd-swinv2-tagger-v3",
}


@dataclass
class WD14TagOptions:
    repo_id: str = DEFAULT_REPO
    model_dir: str = "wd14_tagger_model"
    batch_size: int = 4
    general_threshold: float = 0.35
    character_threshold: float = 0.1
    recursive: bool = False
    remove_underscore: bool = False
    undesired_tags: str = ""
    always_first_tags: str = ""
    append_tags: bool = False
    caption_extension: str = ".txt"
    caption_separator: str = ", "
    character_tags_first: bool = True
    force_download: bool = False


def _glob_images(dir_path: Path, recursive: bool) -> list[Path]:
    exts = set(COMMON_IMAGE_EXTENSIONS)
    if recursive:
        paths = [p for p in dir_path.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    else:
        paths = [p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in exts]
    return sorted(set(paths))


def _preprocess_image(image: Image.Image) -> np.ndarray:
    arr = np.array(image.convert("RGB"))
    arr = arr[:, :, ::-1]  # RGB → BGR

    size = max(arr.shape[0:2])
    pad_x = size - arr.shape[1]
    pad_y = size - arr.shape[0]
    pad_l = pad_x // 2
    pad_t = pad_y // 2
    arr = np.pad(
        arr,
        ((pad_t, pad_y - pad_t), (pad_l, pad_x - pad_l), (0, 0)),
        mode="constant",
        constant_values=255,
    )

    if size > IMAGE_SIZE:
        arr = cv2.resize(arr, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_AREA)
    else:
        arr = cv2.resize(arr, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_CUBIC)

    return arr.astype(np.float32)


def _download_model(repo_id: str, model_dir: str, force: bool) -> Path:
    location = Path(model_dir) / repo_id.replace("/", "_")
    if location.is_dir() and (location / "model.onnx").is_file() and not force:
        logger.info("使用本地模型: %s", location)
        return location

    location.mkdir(parents=True, exist_ok=True)
    logger.info("下载 WD14 模型: %s", repo_id)
    for filename in ("selected_tags.csv", "model.onnx"):
        hf_hub_download(
            repo_id,
            filename,
            cache_dir=str(location),
            force_download=force,
            force_filename=filename,
        )
    return location


def _load_tag_lists(
    model_location: Path,
    opts: WD14TagOptions,
) -> tuple[list[str], list[str], list[str]]:
    csv_path = model_location / CSV_FILE
    with csv_path.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    header = rows[0]
    data = rows[1:]
    assert header[:3] == ["tag_id", "name", "category"], f"unexpected csv: {header}"

    rating_tags = [r[1] for r in data if r[2] == "9"]
    general_tags = [r[1] for r in data if r[2] == "0"]
    character_tags = [r[1] for r in data if r[2] == "4"]

    if opts.remove_underscore:
        rating_tags = [t.replace("_", " ") if len(t) > 3 else t for t in rating_tags]
        general_tags = [t.replace("_", " ") if len(t) > 3 else t for t in general_tags]
        character_tags = [t.replace("_", " ") if len(t) > 3 else t for t in character_tags]

    return rating_tags, general_tags, character_tags


def _create_session(onnx_path: Path):
    import torch  # noqa: F401 — 加载 CUDA 库供 onnxruntime 使用
    import onnxruntime as ort

    providers = ort.get_available_providers()
    if "CUDAExecutionProvider" in providers:
        chosen = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    elif "ROCMExecutionProvider" in providers:
        chosen = ["ROCMExecutionProvider", "CPUExecutionProvider"]
    else:
        chosen = ["CPUExecutionProvider"]

    logger.info("ONNX Runtime providers: %s", chosen)
    return ort.InferenceSession(str(onnx_path), providers=chosen)


def _tags_from_prob(
    prob: np.ndarray,
    rating_tags: list[str],
    general_tags: list[str],
    character_tags: list[str],
    opts: WD14TagOptions,
    undesired: set[str],
    always_first: list[str] | None,
) -> str:
    combined: list[str] = []
    sep = opts.caption_separator

    for i, p in enumerate(prob[4:]):
        if i < len(general_tags) and p >= opts.general_threshold:
            name = general_tags[i]
            if name not in undesired:
                combined.append(name)
        elif i >= len(general_tags) and p >= opts.character_threshold:
            name = character_tags[i - len(general_tags)]
            if name not in undesired:
                if opts.character_tags_first:
                    combined.insert(0, name)
                else:
                    combined.append(name)

    if always_first:
        for tag in always_first:
            if tag in combined:
                combined.remove(tag)
            combined.insert(0, tag)

    return sep.join(combined)


def tag_images_wd14(
    train_data_dir: str | Path,
    options: WD14TagOptions | None = None,
) -> JobResult:
    """
    批量 WD14 打标：为目录内每张图片生成同名 .txt caption 文件。
    """
    opts = options or WD14TagOptions()
    data_dir = Path(train_data_dir)

    if not data_dir.is_dir():
        return JobResult(ok=False, message=f"目录不存在: {data_dir}")

    try:
        import onnxruntime  # noqa: F401
    except ImportError as e:
        return JobResult(
            ok=False,
            message="缺少依赖 onnxruntime，请执行: pip install onnxruntime-gpu 或 onnxruntime",
            errors=[str(e)],
        )

    image_paths = _glob_images(data_dir, opts.recursive)
    if not image_paths:
        return JobResult(ok=False, message="未找到可打标的图片文件")

    try:
        model_location = _download_model(opts.repo_id, opts.model_dir, opts.force_download)
        rating_tags, general_tags, character_tags = _load_tag_lists(model_location, opts)
        session = _create_session(model_location / "model.onnx")
        input_name = session.get_inputs()[0].name
    except Exception as e:
        return JobResult(ok=False, message=f"模型加载失败: {e}", errors=[str(e)])

    stripped_sep = opts.caption_separator.strip()
    undesired = {t.strip() for t in opts.undesired_tags.split(stripped_sep) if t.strip()}
    always_first = None
    if opts.always_first_tags.strip():
        always_first = [t.strip() for t in opts.always_first_tags.split(stripped_sep) if t.strip()]

    processed = 0
    errors: list[str] = []
    details: list[str] = []
    outputs: list[Path] = []

    batch: list[tuple[Path, np.ndarray]] = []

    def flush_batch() -> None:
        nonlocal processed
        if not batch:
            return

        imgs = np.array([im for _, im in batch])
        try:
            probs = session.run(None, {input_name: imgs})[0]
        except Exception as e:
            for path, _ in batch:
                errors.append(f"{path.name}: 推理失败 {e}")
            batch.clear()
            return

        for (image_path, _), prob in zip(batch, probs):
            caption_path = image_path.with_suffix(opts.caption_extension)
            tag_text = _tags_from_prob(
                prob,
                rating_tags,
                general_tags,
                character_tags,
                opts,
                undesired,
                always_first,
            )

            if opts.append_tags and caption_path.is_file():
                existing = caption_path.read_text(encoding="utf-8").strip()
                existing_tags = [t.strip() for t in existing.split(stripped_sep) if t.strip()]
                new_tags = [t for t in tag_text.split(stripped_sep) if t.strip() and t.strip() not in existing_tags]
                tag_text = stripped_sep.join(existing_tags + new_tags)

            try:
                caption_path.write_text(tag_text + "\n", encoding="utf-8")
                processed += 1
                outputs.append(caption_path)
                details.append(f"{image_path.name} → {caption_path.name} ({len(tag_text.split(stripped_sep))} tags)")
            except Exception as e:
                errors.append(f"{image_path.name}: 写入失败 {e}")

        batch.clear()

    for image_path in image_paths:
        try:
            with Image.open(image_path) as img:
                arr = _preprocess_image(img)
            batch.append((image_path, arr))
        except Exception as e:
            errors.append(f"{image_path.name}: 读取失败 {e}")
            continue

        if len(batch) >= opts.batch_size:
            flush_batch()

    flush_batch()

    ok = processed > 0
    return JobResult(
        ok=ok,
        message=f"打标完成：{processed}/{len(image_paths)} 张"
        if ok
        else "打标失败，未成功处理任何图片",
        processed=processed,
        skipped=len(image_paths) - processed - len(errors),
        errors=errors,
        details=details[:200],
        outputs=outputs,
    )
