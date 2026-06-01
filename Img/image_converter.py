# =============================================================================
# 脚本名称: image_converter.py
# 功能描述: 图形界面图片批量转换工具
#           - 支持多种格式转 PNG（含 HEIC/HEIF，需 pillow-heif）
#           - 按目标面积智能匹配 64 倍数尺寸，等比缩放并透明居中填充
#           - 可选递归处理子目录，各文件夹内独立重命名为 0.png, 1.png...
# 依赖库:   Pillow, tkinter（标准库）, pillow-heif（可选）
# 使用方法: 直接运行本脚本，在 GUI 中选择路径并设置参数
# =============================================================================

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from img_tools._bootstrap import ensure_repo_on_path

ensure_repo_on_path()

try:
    from PIL import Image  # noqa: F401 — 启动时检查 Pillow
except ImportError:
    print("❌ 请先安装 Pillow: pip install Pillow")
    raise SystemExit(1)

from img_tools.convert import process_all


class ImageConverterApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("双双的图片工坊 Pro Max ✨")
        self.root.geometry("550x450")
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="📸 目标路径 (图片来源):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.target_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.target_var, width=40).grid(
            row=1, column=0, columnspan=2, sticky=tk.EW
        )
        ttk.Button(main_frame, text="浏览", command=self.browse_target).grid(row=1, column=2, padx=5)

        ttk.Label(main_frame, text="📂 输出路径 (PNG结果):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_var, width=40).grid(
            row=3, column=0, columnspan=2, sticky=tk.EW
        )
        ttk.Button(main_frame, text="浏览", command=self.browse_output).grid(row=3, column=2, padx=5)

        option_frame = ttk.LabelFrame(main_frame, text=" 处理选项 ", padding="10")
        option_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=10)

        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            option_frame, text="包含子文件夹 (递归处理)", variable=self.recursive_var
        ).pack(side=tk.LEFT, padx=10)

        size_frame = ttk.LabelFrame(
            main_frame, text=" 智能目标面积基准 (程序会自动匹配64的倍数) ", padding="10"
        )
        size_frame.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=10)

        ttk.Label(size_frame, text="基准宽:").pack(side=tk.LEFT, padx=5)
        self.width_var = tk.StringVar(value="1024")
        ttk.Entry(size_frame, textvariable=self.width_var, width=8).pack(side=tk.LEFT, padx=5)

        ttk.Label(size_frame, text="×  基准高:").pack(side=tk.LEFT, padx=5)
        self.height_var = tk.StringVar(value="1024")
        ttk.Entry(size_frame, textvariable=self.height_var, width=8).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=15)
        ttk.Button(btn_frame, text="🚀 启动魔法处理", command=self.run_convert).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text="退出", command=self.root.quit).pack(side=tk.LEFT, padx=10)

        self.status_var = tk.StringVar(value="准备就绪，杰西随时可以下发任务啦 🫡")
        ttk.Label(main_frame, textvariable=self.status_var, foreground="gray").grid(
            row=7, column=0, columnspan=3, sticky=tk.W
        )

    def browse_target(self):
        path = filedialog.askdirectory()
        if path:
            self.target_var.set(path)

    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)

    def run_convert(self):
        try:
            w, h = int(self.width_var.get()), int(self.height_var.get())
            if w <= 0 or h <= 0:
                raise ValueError
            target_area = w * h
        except ValueError:
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
            result = process_all(target, output, target_area, is_rec)
            converted = result.outputs
            errors = result.errors

            if not result.ok and not converted:
                messagebox.showerror("出错啦", result.message)
            elif errors:
                messagebox.showwarning(
                    "完成", f"处理了 {len(converted)} 张，但有 {len(errors)} 个异常。"
                )
            else:
                messagebox.showinfo(
                    "大功告成", f"🎉 任务圆满完成！共完美转换 {len(converted)} 张图片。"
                )
            self.status_var.set(f"最近任务：处理 {len(converted)} 张成功 ✅")
        except Exception as e:
            messagebox.showerror("崩溃了", f"程序报错：{e}")
            self.status_var.set("处理失败 ❌")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ImageConverterApp()
    app.run()
