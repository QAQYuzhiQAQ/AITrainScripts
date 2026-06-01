# =============================================================================
# 脚本名称: rename_images_numbered.py
# 功能描述: 批量将文件夹内图片重命名为「前缀 + 补零编号 + 扩展名」
#           例如 image_001.png, image_002.png（支持自然排序）
# 依赖库:   natsort（pip install natsort）
# 使用方法: 修改底部 FOLDER 等参数，先 dry_run=True 预览，确认后改为 False
# =============================================================================

import os
from pathlib import Path
import natsort

def batch_rename_images(
    folder_path: str,
    prefix: str = "",          # 文件名前缀，例如 "char_" 或 ""
    start_num: int = 1,        # 从几开始编号
    digits: int = 3,           # 编号位数（3 → 001, 4 → 0001）
    extensions: tuple = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"),  # 支持的图片格式
    dry_run: bool = True       # True = 只预览不改名，False = 真正重命名
):
    """
    批量将文件夹内图片重命名为 prefix + 编号（带前导零） + 扩展名
    示例：image_001.png, image_002.png, ..., image_099.png
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"错误：{folder} 不是有效文件夹")
        return

    # 获取所有图片文件，按自然顺序排序
    image_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in extensions]
    image_files = natsort.natsorted(image_files)  # 自然排序，非常重要！

    if not image_files:
        print("文件夹中没有找到图片文件")
        return

    print(f"找到 {len(image_files)} 张图片文件")
    print("预览重命名结果（dry_run 模式）：\n")

    renamed_count = 0
    for i, old_path in enumerate(image_files, start=start_num):
        # 生成新文件名：前缀 + 编号（补零） + 扩展名
        number_str = f"{i:0{digits}d}"   # 例如 i=5, digits=3 → "005"
        new_name = f"{prefix}{number_str}{old_path.suffix}"
        new_path = old_path.parent / new_name

        print(f"{old_path.name}  →  {new_name}")

        if not dry_run:
            try:
                os.rename(old_path, new_path)
                renamed_count += 1
            except Exception as e:
                print(f"重命名失败 {old_path.name}：{e}")

    if dry_run:
        print("\n以上仅为预览！文件尚未修改。")
        print("确认无误后，将 dry_run=False 再运行一次即可真正重命名。")
    else:
        print(f"\n完成！成功重命名 {renamed_count} 个文件。")

# ===================== 使用示例 =====================
if __name__ == "__main__":
    # 修改这里为你自己的文件夹路径
    FOLDER = r"C:\AI绘图合集\2026\2026.3"          # ← 改成你的路径（Windows 用 r"..." 或双反斜杠）
    # FOLDER = "/home/yuzhi/anime_images"            # Linux/Mac 示例

    batch_rename_images(
        folder_path=FOLDER,
        prefix="",          # 可改成 ""（空） 或 "角色名_" 等
        start_num=1,            # 从 1 开始
        digits=3,               # 001 ~ 999
        dry_run=False            # 先预览！改成 False 才真的改名
    )