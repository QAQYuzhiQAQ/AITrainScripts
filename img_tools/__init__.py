"""Img 图片预处理核心库（无 UI）。"""

from img_tools.common import JobResult, ensure_dir, register_heif_opener
from img_tools.convert import (
    SUPPORTED_FORMATS,
    get_optimal_target_size,
    process_all,
    rename_files_in_each_dir,
    resize_with_padding,
)
from img_tools.crop_2k import TARGET_SIZE, CROP_BOX, crop_2k_png_recursive
from img_tools.filter_2k import TARGET_HEIGHT, TARGET_WIDTH, filter_2k_images
from img_tools.rename import batch_rename_numbered, rename_sequential
from img_tools.resize import resize_fixed_canvas, resize_png_center_batch
from img_tools.workflow import (
    RenameMode,
    ResizeMode,
    WorkflowRenameOptions,
    run_prepare_workflow,
)

__all__ = [
    "JobResult",
    "SUPPORTED_FORMATS",
    "TARGET_SIZE",
    "CROP_BOX",
    "TARGET_WIDTH",
    "TARGET_HEIGHT",
    "ensure_dir",
    "register_heif_opener",
    "get_optimal_target_size",
    "resize_with_padding",
    "resize_fixed_canvas",
    "rename_files_in_each_dir",
    "process_all",
    "crop_2k_png_recursive",
    "filter_2k_images",
    "batch_rename_numbered",
    "rename_sequential",
    "resize_png_center_batch",
    "RenameMode",
    "ResizeMode",
    "WorkflowRenameOptions",
    "run_prepare_workflow",
]
