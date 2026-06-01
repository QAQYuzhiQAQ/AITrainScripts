# =============================================================================
# 脚本名称: remove_non_2k_images.py
# 功能描述: 递归扫描目录，删除尺寸不是 2560×1440 的图片文件
#           保留符合 2K 标准的 PNG/JPG/JPEG/BMP/WEBP 图片
# 依赖库:   Pillow
# 使用方法: 修改底部 path_to_clean 路径，运行后输入 y 确认删除
# 注意:     此操作不可逆，运行前请备份重要文件
# =============================================================================

import os
from PIL import Image


def filter_images(target_dir):
    # 设定我们心目中的“完美尺寸”
    target_width = 2560
    target_height = 1440

    print(f"🚀 开始巡检目录: {target_dir}")
    print(f"📸 目标尺寸: {target_width}x{target_height}\n")

    # 遍历文件夹及其子文件夹
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            file_path = os.path.join(root, file)

            # 只检查常见的图片格式
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size

                        # 判断尺寸是否符合要求
                        if width == target_width and height == target_height:
                            print(f"✅ 保留: {file} ({width}x{height})")
                        else:
                            print(f"🗑️ 删除: {file} (尺寸为 {width}x{height})")
                            img.close()  # 确保关闭文件流后再删除
                            os.remove(file_path)
                except Exception as e:
                    print(f"❌ 无法处理文件 {file}: {e}")


if __name__ == "__main__":
    # 把这里的路径换成你存放图片的实际路径哦！
    path_to_clean = r'L:\Game\Ero\Amakano3\res\img\image\ev'

    # 再次确认，防止误删！
    confirm = input(f"确认要清理 {path_to_clean} 下非 2K 尺寸的图片吗？(y/n): ")
    if confirm.lower() == 'y':
        filter_images(path_to_clean)
        print("\n✨ 清理完毕！现在的文件夹里全是完美的 2K 壁纸啦！")
    else:
        print("\n✋ 操作已取消，文件安全~")