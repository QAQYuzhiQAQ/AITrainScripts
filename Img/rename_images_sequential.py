# =============================================================================
# 脚本名称: rename_images_sequential.py
# 功能描述: 将文件夹内图片按顺序重命名为「序号 + 扩展名」
#           例如 42.png, 43.png（从指定起始序号递增）
# 依赖库:   无（标准库）
# 使用方法: 修改底部 target_folder 和 start_number，运行本脚本
# =============================================================================

import os


def rename_images(folder_path, start_index):
    # 支持的图片后缀
    valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')

    # 获取文件夹内所有文件
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)]

    current_index = start_index

    for filename in files:
        name_part, extension = os.path.splitext(filename)

        # 判断文件名长度是否超过8个字符
        if len(name_part) > 0:
            new_name = f"{current_index}{extension}"
            old_file = os.path.join(folder_path, filename)
            new_file = os.path.join(folder_path, new_name)

            # 简单处理：如果新名字已经存在，跳过或者做个小标记（这里为了安全默认跳过）
            if os.path.exists(new_file):
                print(f"⚠️ 哎呀，{new_name} 已经存在啦，跳过这个文件哦：{filename}")
                continue

            os.rename(old_file, new_file)
            print(f"✅ 完成重命名：{filename} -> {new_name}")
            current_index += 1
        else:
            print(f"⏭️ {filename} 长度没超标，跳过~")


# --- 使用方式 ---
# 记得把路径改成你电脑上的真实路径哦！
target_folder = r'C:\Document\参考图\LoRATrain\Authenticity\ouput\25d\day4'
start_number = 42  # 你想要的起始序号

rename_images(target_folder, start_number)