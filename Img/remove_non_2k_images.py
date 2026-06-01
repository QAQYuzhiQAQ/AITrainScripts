# =============================================================================
# 脚本名称: remove_non_2k_images.py
# 功能描述: 递归扫描目录，删除尺寸不是 2560×1440 的图片文件
#           保留符合 2K 标准的 PNG/JPG/JPEG/BMP/WEBP 图片
# 依赖库:   Pillow
# 使用方法: 修改底部 path_to_clean 路径，运行后输入 y 确认删除
# 注意:     此操作不可逆，运行前请备份重要文件
# =============================================================================

from img_tools._bootstrap import ensure_repo_on_path
from img_tools.common import print_job_result
from img_tools.filter_2k import filter_2k_images

ensure_repo_on_path()

if __name__ == "__main__":
    path_to_clean = r"L:\Game\Ero\Amakano3\res\img\image\ev"

    preview = filter_2k_images(path_to_clean, dry_run=True)
    print_job_result(preview)
    print()

    confirm = input(f"确认要清理 {path_to_clean} 下非 2K 尺寸的图片吗？(y/n): ")
    if confirm.lower() == "y":
        result = filter_2k_images(path_to_clean, dry_run=False)
        print_job_result(result)
        print("\n✨ 清理完毕！")
    else:
        print("\n✋ 操作已取消，文件安全~")
