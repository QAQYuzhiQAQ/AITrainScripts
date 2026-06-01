# =============================================================================
# 脚本名称: crop_2k_png.py
# 功能描述: 递归扫描目录及子目录，将尺寸为 2560×1440 的 PNG 图片
#           按固定区域 (320, 0, 2240, 1440) 裁剪后输出，保持原有目录结构
# 依赖库:   Pillow
# 使用方法: 修改底部 INPUT_DIR / OUTPUT_DIR 路径，运行本脚本
# =============================================================================

import os
from PIL import Image


def recursive_smart_crop(input_root, output_root):
    # 目标参数
    TARGET_SIZE = (2560, 1440)
    CROP_BOX = (320, 0, 2240, 1440)

    processed_count = 0
    skipped_count = 0

    print(f"🚀 开启‘全路径搜寻’模式...")
    print(f"📂 扫描起点: {os.path.abspath(input_root)}\n")

    # os.walk 会遍历所有子目录
    for root, dirs, files in os.walk(input_root):
        for filename in files:
            if not filename.lower().endswith('.png'):
                continue

            # 构建完整读取路径
            img_path = os.path.join(root, filename)

            # 计算对应的输出子目录
            relative_path = os.path.relpath(root, input_root)
            target_sub_dir = os.path.join(output_root, relative_path)

            try:
                with Image.open(img_path) as img:
                    if img.size == TARGET_SIZE:
                        # 只有在处理前才创建对应的输出子文件夹
                        if not os.path.exists(target_sub_dir):
                            os.makedirs(target_sub_dir)

                        save_path = os.path.join(target_sub_dir, filename)
                        img.crop(CROP_BOX).save(save_path)

                        print(f"✅ [处理] {os.path.join(relative_path, filename)}")
                        processed_count += 1
                    else:
                        print(f"⚠️ [跳过] {os.path.join(relative_path, filename)} (尺寸: {img.size})")
                        skipped_count += 1

            except Exception as e:
                print(f"❌ [错误] 无法读取 {filename}: {e}")

    print("-" * 40)
    print(f"✨ 任务圆满完成！")
    print(f"📦 共处理图片: {processed_count} 张")
    print(f"⏭️ 自动跳过图片: {skipped_count} 张")
    print(f"📂 结果存放在: {output_root}")


# --- 运行配置 ---
INPUT_DIR = 'C:\Document\参考图\LoRATrain\Lilith\Tamanin'  # 包含子目录的源文件夹
OUTPUT_DIR = 'C:\Document\参考图\LoRATrain\Lilith\output'  # 处理后的目标文件夹

if __name__ == "__main__":
    recursive_smart_crop(INPUT_DIR, OUTPUT_DIR)