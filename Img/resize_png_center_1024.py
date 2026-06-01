# =============================================================================
# 脚本名称: resize_png_center_1024.py
# 功能描述: 将当前目录下所有 PNG 图片等比缩放至最大边 1024，
#           居中放置于 1024×1024 透明画布上，输出到 new/ 文件夹
# 依赖库:   Pillow
# 使用方法: 将 PNG 文件放在脚本同目录，运行本脚本
# =============================================================================

import os
from PIL import Image
from PIL.Image import Resampling

# 输出文件夹
OUTPUT_DIR = 'new'

# 最大尺寸
MAX_SIZE = 1024

# 创建输出文件夹
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 遍历当前目录下的所有 PNG 文件（不进入子目录）
for filename in os.listdir('.'):
    if not filename.lower().endswith('.png'):
        continue

    # 确保是文件而不是目录
    if not os.path.isfile(filename):
        continue

    # 打开图像
    img = Image.open(filename)
    w, h = img.size

    # 计算缩放比例，使较大边等于 MAX_SIZE
    scale = MAX_SIZE / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    # 按比例缩放
    resized = img.resize((new_w, new_h), Resampling.LANCZOS)

    # 创建透明背景的新图像，用于填充到 MAX_SIZE x MAX_SIZE
    canvas = Image.new('RGBA', (MAX_SIZE, MAX_SIZE), (0, 0, 0, 0))

    # 将缩放后的图像粘贴到中心
    offset_x = (MAX_SIZE - new_w) // 2
    offset_y = (MAX_SIZE - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))

    # 输出路径：只保留文件名
    output_file_path = os.path.join(OUTPUT_DIR, filename)

    # 保存到输出目录
    canvas.save(output_file_path)
    print(f"Processed {filename} -> {output_file_path}")

print("所有图像处理完成，已保存到 'new' 文件夹。")
