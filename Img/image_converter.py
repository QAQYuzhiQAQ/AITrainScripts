# =============================================================================
# 脚本名称: image_converter.py
# 功能描述: 图形界面图片批量转换工具
#           - 支持多种格式转 PNG（含 HEIC/HEIF，需 pillow-heif）
#           - 按目标面积智能匹配 64 倍数尺寸，等比缩放并透明居中填充
#           - 可选递归处理子目录，各文件夹内独立重命名为 0.png, 1.png...
# 依赖库:   Pillow, tkinter（标准库）, pillow-heif（可选）
# 使用方法: 直接运行本脚本，在 GUI 中选择路径并设置参数
# =============================================================================

import os
import time
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    from PIL import Image

    # 尝试引入 HEIF 支持
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:
        pass
except ImportError:
    print("❌ 请先安装 Pillow: pip install Pillow")
    exit(1)

# 支持的图片格式
SUPPORTED_FORMATS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.tiff', '.tif', '.ico', '.jfif', '.jpe', '.heic', '.heif', '.jp2'
}


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def get_optimal_target_size(orig_w, orig_h, target_area):
    """根据原图比例，计算最接近 target_area 且长宽均为 64 倍数的尺寸"""
    if orig_w <= 0 or orig_h <= 0:
        return 64, 64

    aspect_ratio = orig_w / orig_h

    # 按照目标面积和原图比例，计算理想的长宽
    ideal_h = math.sqrt(target_area / aspect_ratio)
    ideal_w = ideal_h * aspect_ratio

    # 四舍五入到最接近的 64 的倍数 (最小为 64)
    target_w = max(64, round(ideal_w / 64) * 64)
    target_h = max(64, round(ideal_h / 64) * 64)

    return target_w, target_h


def resize_with_padding(img, target_area):
    """动态匹配64倍数尺寸，保持比例缩放并在透明背景上居中"""
    orig_w, orig_h = img.size
    if orig_w <= 0 or orig_h <= 0:
        return None

    # 1. 获取智能匹配的目标分辨率
    target_width, target_height = get_optimal_target_size(orig_w, orig_h, target_area)

    # 2. 计算缩放比例，保证图片能完整放进目标画布
    scale = min(target_width / orig_w, target_height / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    # 3. 缩放并居中贴到透明画布上
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 0))
    paste_x = (target_width - new_w) // 2
    paste_y = (target_height - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))

    return canvas


def rename_files_in_each_dir(output_root):
    """在每个涉及到的文件夹内部独立进行 0.png, 1.png... 的重命名"""
    ts = int(time.time())
    for root, dirs, files in os.walk(output_root):
        current_dir = Path(root)
        png_files = sorted([f for f in current_dir.glob('*.png')], key=lambda p: p.name)

        if not png_files:
            continue

        temp_mappings = []
        for i, f in enumerate(png_files):
            temp_name = f"__tmp_{ts}_{i}.png"
            temp_path = current_dir / temp_name
            f.rename(temp_path)
            temp_mappings.append((temp_path, i))

        for temp_path, i in temp_mappings:
            final_name = f"{i}.png"
            temp_path.rename(current_dir / final_name)


def process_all(target_path, output_path, target_area, recursive):
    """核心逻辑：可选递归处理 + 保持结构 + 独立重命名"""
    target_root = Path(target_path)
    output_root = Path(output_path)

    if not target_root.exists():
        return False, [], [], f"目标路径不存在哦～"

    processed_list = []
    errors = []

    # 准备遍历逻辑
    if recursive:
        all_files_info = []
        for root, _, files in os.walk(target_root):
            for f in files:
                all_files_info.append(Path(root) / f)
    else:
        all_files_info = [f for f in target_root.iterdir() if f.is_file()]

    # 1. 执行转换与裁剪
    for file_path in all_files_info:
        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            continue

        relative_path = file_path.relative_to(target_root)
        target_out_file = output_root / relative_path.with_suffix('.png')
        ensure_dir(target_out_file.parent)

        try:
            with Image.open(file_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                # 传入 target_area 替代固定的 width/height
                result = resize_with_padding(img, target_area)
                if result:
                    result.save(target_out_file, 'PNG')
                    processed_list.append(target_out_file)
        except Exception as e:
            errors.append(f"{file_path.name}: {e}")

    # 2. 独立重命名
    if processed_list:
        try:
            rename_files_in_each_dir(output_root)
        except Exception as e:
            errors.append(f"重命名环节出错: {e}")

    success = len(processed_list) > 0
    return success, processed_list, errors, None if processed_list else "没找到支持的图片文件呢 🥺"


class ImageConverterApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("双双的图片工坊 Pro Max ✨")
        self.root.geometry("550x450")
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 路径选择
        ttk.Label(main_frame, text="📸 目标路径 (图片来源):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.target_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.target_var, width=40).grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        ttk.Button(main_frame, text="浏览", command=self.browse_target).grid(row=1, column=2, padx=5)

        ttk.Label(main_frame, text="📂 输出路径 (PNG结果):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_var, width=40).grid(row=3, column=0, columnspan=2, sticky=tk.EW)
        ttk.Button(main_frame, text="浏览", command=self.browse_output).grid(row=3, column=2, padx=5)

        # 功能开关区
        option_frame = ttk.LabelFrame(main_frame, text=" 处理选项 ", padding="10")
        option_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=10)

        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(option_frame, text="包含子文件夹 (递归处理)", variable=self.recursive_var).pack(side=tk.LEFT,
                                                                                                        padx=10)

        # 尺寸设置 (调整为目标总像素计算模式)
        size_frame = ttk.LabelFrame(main_frame, text=" 智能目标面积基准 (程序会自动匹配64的倍数) ", padding="10")
        size_frame.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=10)

        ttk.Label(size_frame, text="基准宽:").pack(side=tk.LEFT, padx=5)
        self.width_var = tk.StringVar(value="1024")
        ttk.Entry(size_frame, textvariable=self.width_var, width=8).pack(side=tk.LEFT, padx=5)

        ttk.Label(size_frame, text="×  基准高:").pack(side=tk.LEFT, padx=5)
        self.height_var = tk.StringVar(value="1024")
        ttk.Entry(size_frame, textvariable=self.height_var, width=8).pack(side=tk.LEFT, padx=5)

        # 按钮区
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=15)
        ttk.Button(btn_frame, text="🚀 启动魔法处理", command=self.run_convert).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="退出", command=self.root.quit).pack(side=tk.LEFT, padx=10)

        # 状态栏
        self.status_var = tk.StringVar(value="准备就绪，杰西随时可以下发任务啦 🫡")
        ttk.Label(main_frame, textvariable=self.status_var, foreground="gray").grid(row=7, column=0, columnspan=3,
                                                                                    sticky=tk.W)

    def browse_target(self):
        path = filedialog.askdirectory()
        if path: self.target_var.set(path)

    def browse_output(self):
        path = filedialog.askdirectory()
        if path: self.output_var.set(path)

    def run_convert(self):
        try:
            w, h = int(self.width_var.get()), int(self.height_var.get())
            if w <= 0 or h <= 0: raise ValueError
            target_area = w * h  # 计算出总像素目标值
        except:
            messagebox.showerror("哎呀", "基准宽度和高度得是正整数哦！")
            return

        target, output = self.target_var.get().strip(), self.output_var.get().strip()
        is_rec = self.recursive_var.get()

        if not target or not output:
            messagebox.showwarning("提示", "宝，请先选好路径哟～")
            return

        self.status_var.set("全力工作中，双双正在施展魔法... 🔥")
        self.root.update()

        try:
            # 传入的是 target_area 而不是具体的长宽了
            success, converted, errors, err_msg = process_all(target, output, target_area, is_rec)
            if err_msg and not converted:
                messagebox.showerror("出错啦", err_msg)
            elif errors:
                messagebox.showwarning("完成", f"处理了 {len(converted)} 张，但有 {len(errors)} 个异常。")
            else:
                messagebox.showinfo("大功告成", f"🎉 任务圆满完成！共完美转换 {len(converted)} 张图片。")
            self.status_var.set(f"最近任务：处理 {len(converted)} 张成功 ✅")
        except Exception as e:
            messagebox.showerror("崩溃了", f"程序报错：{e}")
            self.status_var.set("处理失败 ❌")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ImageConverterApp()
    app.run()