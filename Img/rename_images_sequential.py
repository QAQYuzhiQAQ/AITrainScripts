# =============================================================================
# 脚本名称: rename_images_sequential.py
# 功能描述: 将文件夹内图片按顺序重命名为「序号 + 扩展名」
#           例如 42.png, 43.png（从指定起始序号递增）
# 依赖库:   无（标准库）
# 使用方法: 修改底部 target_folder 和 start_number，运行本脚本
# =============================================================================

from img_tools._bootstrap import ensure_repo_on_path
from img_tools.common import print_job_result
from img_tools.rename import rename_sequential

ensure_repo_on_path()

if __name__ == "__main__":
    target_folder = r"C:\Document\参考图\LoRATrain\Authenticity\ouput\25d\day4"
    start_number = 42

    result = rename_sequential(target_folder, start_number, dry_run=False)
    print_job_result(result)
