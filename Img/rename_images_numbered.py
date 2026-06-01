# =============================================================================
# 脚本名称: rename_images_numbered.py
# 功能描述: 批量将文件夹内图片重命名为「前缀 + 补零编号 + 扩展名」
#           例如 image_001.png, image_002.png（支持自然排序）
# 依赖库:   natsort（pip install natsort）
# 使用方法: 修改底部 FOLDER 等参数，先 dry_run=True 预览，确认后改为 False
# =============================================================================

from img_tools._bootstrap import ensure_repo_on_path
from img_tools.common import print_job_result
from img_tools.rename import batch_rename_numbered

ensure_repo_on_path()

if __name__ == "__main__":
    FOLDER = r"C:\AI绘图合集\2026\2026.3"

    dry_run = True  # 先预览；确认后改为 False

    result = batch_rename_numbered(
        folder_path=FOLDER,
        prefix="",
        start_num=1,
        digits=3,
        dry_run=dry_run,
    )
    print_job_result(result)
    if dry_run:
        print("\n以上仅为预览！将 dry_run=False 再运行即可真正重命名。")
