# =============================================================================
# 脚本名称: resize_png_center_1024.py
# 功能描述: 将指定目录下所有 PNG 图片等比缩放至最大边 1024，
#           居中放置于 1024×1024 透明画布上，输出到 new/ 文件夹
# 依赖库:   Pillow
# 使用方法: 修改底部 INPUT_DIR，或将 PNG 放在脚本同目录后运行
# =============================================================================

from pathlib import Path

from img_tools._bootstrap import ensure_repo_on_path
from img_tools.common import print_job_result
from img_tools.resize import resize_png_center_batch

ensure_repo_on_path()

INPUT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = INPUT_DIR / "new"

if __name__ == "__main__":
    result = resize_png_center_batch(INPUT_DIR, OUTPUT_DIR, canvas_size=1024, recursive=False)
    print_job_result(result)
