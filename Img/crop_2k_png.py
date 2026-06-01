# =============================================================================
# 脚本名称: crop_2k_png.py
# 功能描述: 递归扫描目录及子目录，将尺寸为 2560×1440 的 PNG 图片
#           按固定区域 (320, 0, 2240, 1440) 裁剪后输出，保持原有目录结构
# 依赖库:   Pillow
# 使用方法: 修改底部 INPUT_DIR / OUTPUT_DIR 路径，运行本脚本
# =============================================================================

from img_tools._bootstrap import ensure_repo_on_path
from img_tools.common import print_job_result
from img_tools.crop_2k import crop_2k_png_recursive

ensure_repo_on_path()

INPUT_DIR = r"C:\Document\参考图\LoRATrain\Lilith\Tamanin"
OUTPUT_DIR = r"C:\Document\参考图\LoRATrain\Lilith\output"

if __name__ == "__main__":
    result = crop_2k_png_recursive(INPUT_DIR, OUTPUT_DIR)
    print_job_result(result)
