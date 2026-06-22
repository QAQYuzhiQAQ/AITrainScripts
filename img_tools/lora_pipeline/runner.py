"""
LoRA 角色训练完整流水线（8 步）。

用户准备 characterABC/ 并放入原始图片后，由本模块依次执行：
  1. 确保 res / output / {n}_output 目录存在
  2. 将根目录原始图片移动到 res/
  3–4. 裁切转化 res → output/{n}_output 并重命名
  5. WD14 打标
  6. Caption 规则清洗
  7. 以 output/ 为 train_data_dir 启动 LoRA 训练
  8. 返回完成提示
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from img_tools.caption import (
    CaptionCleanOptions,
    clean_captions_in_dir,
    get_tag_undesired_for_preset,
    get_trigger_for_preset,
)
from img_tools.common import JobResult
from img_tools.lora_pipeline.paths import (
    ensure_structure,
    list_root_raw_images,
    resolve_paths,
)
from img_tools.lora_train import run_lora_train
from img_tools.tagger import WD14TagOptions, tag_images_wd14
from img_tools.workflow import RenameMode, ResizeMode, WorkflowRenameOptions, run_prepare_workflow

ProgressCallback = Callable[[dict[str, Any], str], None]
TOTAL_STEPS = 8


@dataclass
class LoraPipelineOptions:
    character_root: str
    repeat_count: int = 10
    resize_mode: ResizeMode = ResizeMode.AREA_64
    target_width: int = 1024
    target_height: int = 1024
    rename_prefix: str = ""
    rename_digits: int = 4
    caption_preset: str = "default"
    trigger_word: str = ""
    extra_undesired_tags: str = ""
    tag_general_threshold: float = 0.35
    tag_character_threshold: float = 0.1
    lora_preset: str = "morgana_star_nemesis"
    lora_overrides: dict[str, Any] = field(default_factory=dict)


def _report(cb: ProgressCallback | None, step: int, message: str) -> None:
    if cb:
        cb(
            {
                "step": step,
                "total_steps": TOTAL_STEPS,
                "message": message,
                "percent": round(max(0.0, min(100.0, (step - 1) / TOTAL_STEPS * 100)), 1),
            },
            message,
        )


def _merge_undesired(preset_id: str, extra: str) -> str:
    preset = get_tag_undesired_for_preset(preset_id)
    extra = extra.strip()
    if not extra:
        return preset
    if not preset:
        return extra
    merged = {t.strip() for t in (preset + ", " + extra).split(",") if t.strip()}
    return ", ".join(sorted(merged))


def _fail(
    step: int,
    message: str,
    *,
    errors: list[str] | None = None,
    details: list[str] | None = None,
) -> JobResult:
    return JobResult(
        ok=False,
        message=f"[步骤 {step}] {message}",
        errors=errors or [message],
        details=details or [],
    )


def move_root_images_to_res(character_root: Path) -> tuple[int, list[str]]:
    moved = 0
    details: list[str] = []
    res_dir = character_root / "res"
    res_dir.mkdir(parents=True, exist_ok=True)

    for src in list_root_raw_images(character_root):
        dest = res_dir / src.name
        if dest.exists():
            stem, suffix = src.stem, src.suffix
            n = 1
            while dest.exists():
                dest = res_dir / f"{stem}_{n}{suffix}"
                n += 1
        shutil.move(str(src), str(dest))
        moved += 1
        details.append(f"移动: {src.name} → res/{dest.name}")

    return moved, details


def _count_res_images(res_dir: Path) -> int:
    from img_tools.convert import SUPPORTED_FORMATS

    if not res_dir.is_dir():
        return 0
    return sum(
        1 for f in res_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
    )


def run_lora_pipeline(
    options: LoraPipelineOptions,
    *,
    progress_callback: ProgressCallback | None = None,
) -> JobResult:
    root = Path(options.character_root)
    if not root.is_dir():
        return _fail(1, f"角色目录不存在: {root}")

    paths = resolve_paths(root, options.repeat_count)
    all_details: list[str] = []
    concept_name = paths["concept"].name

    # --- 步骤 1：目录结构 ---
    _report(progress_callback, 1, "步骤 1/8：检查并创建 res / output / 子文件夹…")
    ensure_structure(root, options.repeat_count)
    all_details.append(
        f"目录结构: {root.name}/res, {root.name}/output/{concept_name}"
    )

    # --- 步骤 2：移动到 res ---
    _report(progress_callback, 2, "步骤 2/8：将根目录原始图片移动到 res/…")
    moved, move_details = move_root_images_to_res(root)
    all_details.extend(move_details)
    if moved:
        all_details.append(f"共移动 {moved} 张原始图片到 res/")
    else:
        all_details.append("根目录无待移动图片（可能已在 res/ 中）")

    if _count_res_images(paths["res"]) == 0:
        return _fail(
            2,
            "res/ 中没有可处理的图片。请先将原始资源放入角色目录根下，或确认已移入 res/",
            details=all_details,
        )

    # --- 步骤 3–4：裁切转化 + 重命名到 output/{n}_output ---
    _report(progress_callback, 3, f"步骤 3–4/8：处理 res/ → output/{concept_name} 并重命名…")
    rename = WorkflowRenameOptions(
        mode=RenameMode.NUMBERED,
        prefix=options.rename_prefix,
        digits=options.rename_digits,
        sync_captions=True,
    )
    prepare_result = run_prepare_workflow(
        paths["res"],
        paths["concept"],
        options.target_width,
        options.target_height,
        options.resize_mode,
        recursive=False,
        rename=rename,
    )
    all_details.append("=== 图片处理与重命名 ===")
    all_details.extend(prepare_result.details[:80])
    if not prepare_result.ok or prepare_result.processed == 0:
        prepare_result.message = f"[步骤 3–4 失败] {prepare_result.message}"
        prepare_result.details = all_details + prepare_result.details
        return prepare_result

    # --- 步骤 5：打标 ---
    _report(progress_callback, 5, f"步骤 5/8：对 output/{concept_name} 打标…")
    trigger = options.trigger_word.strip() or get_trigger_for_preset(options.caption_preset)
    tag_opts = WD14TagOptions(
        general_threshold=options.tag_general_threshold,
        character_threshold=options.tag_character_threshold,
        always_first_tags=trigger,
        undesired_tags=_merge_undesired(options.caption_preset, options.extra_undesired_tags),
        recursive=False,
    )
    tag_result = tag_images_wd14(paths["concept"], tag_opts)
    all_details.append("=== WD14 打标 ===")
    all_details.append(tag_result.message)
    all_details.extend(tag_result.details[:50])
    if not tag_result.ok:
        tag_result.message = f"[步骤 5 失败] {tag_result.message}"
        tag_result.details = all_details
        return tag_result

    # --- 步骤 6：Caption 二次清洗 ---
    _report(progress_callback, 6, "步骤 6/8：Caption 规则清洗…")
    clean_opts = CaptionCleanOptions(
        preset=options.caption_preset,
        recursive=False,
        dry_run=False,
        trigger_word=trigger or None,
    )
    clean_result = clean_captions_in_dir(paths["concept"], clean_opts)
    all_details.append("=== Caption 清洗 ===")
    all_details.append(clean_result.message)
    all_details.extend(clean_result.details[:50])
    if not clean_result.ok:
        clean_result.message = f"[步骤 6 失败] {clean_result.message}"
        clean_result.details = all_details
        return clean_result

    # --- 步骤 7：LoRA 训练（train_data_dir = output/） ---
    _report(progress_callback, 7, "步骤 7/8：启动 LoRA 训练（train_data_dir = output/）…")
    train_overrides = dict(options.lora_overrides)
    train_overrides["train_data_dir"] = str(paths["output"])

    def train_progress(prog: dict[str, Any], line: str) -> None:
        if progress_callback:
            merged = {
                "step": 7,
                "total_steps": TOTAL_STEPS,
                "message": prog.get("message") or "训练中…",
                "percent": 75.0 + min(24.0, (float(prog.get("percent") or 0) / 100.0) * 24.0),
                "epoch": prog.get("epoch"),
                "max_epochs": prog.get("max_epochs"),
                "step_num": prog.get("step"),
                "max_steps": prog.get("max_steps"),
                "loss": prog.get("loss"),
            }
            progress_callback(merged, line)

    train_result = run_lora_train(
        options.lora_preset,
        overrides=train_overrides,
        progress_callback=train_progress,
    )
    all_details.append("=== LoRA 训练 ===")
    all_details.extend(train_result.details[-30:])
    if not train_result.ok:
        train_result.message = f"[步骤 7 失败] {train_result.message}"
        train_result.details = all_details
        return train_result

    # --- 步骤 8：完成 ---
    output_name = train_overrides.get("output_name") or options.lora_preset
    output_dir = train_overrides.get("output_dir") or ""
    done_msg = (
        f"训练已完成！LoRA 模型：{output_name}"
        + (f"，保存目录：{output_dir}" if output_dir else "")
        + f"。数据目录：{paths['output']}（含子文件夹 {concept_name}）"
    )
    _report(progress_callback, 8, done_msg)

    return JobResult(
        ok=True,
        message=done_msg,
        processed=prepare_result.processed + tag_result.processed,
        details=all_details,
        outputs=train_result.outputs,
    )
