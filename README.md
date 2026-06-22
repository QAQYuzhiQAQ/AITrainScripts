# AITrainScripts

个人 AI 训练与数据处理脚本集合。图片预处理逻辑集中在 `img_tools/`，可通过 **Web Hub** 或 **命令行** 使用；`Img/` 下保留独立脚本作为薄封装。

## 快速开始（Web Hub）

### 一键启动（Windows / macOS / Linux）

| 系统 | 操作 |
|------|------|
| **Windows** | 双击 [`start_hub.bat`](start_hub.bat) |
| **macOS** | 双击 [`start_hub.command`](start_hub.command)（若被拦截：右键 → 打开） |
| **任意系统** | `python start_hub.py` 或 `./start_hub.sh` |

脚本会自动 `pip install` 依赖并启动服务。**保持终端窗口不要关闭**，浏览器访问：

**http://127.0.0.1:8765**

### 手动启动

```bash
cd AITrainScripts
pip install -r requirements.txt
python -m hub
```

端口在 [`hub/config.py`](hub/config.py) 配置（默认 `8765`）。

### 无法打开页面（`ERR_CONNECTION_REFUSED`）

表示本机 **8765 端口没有服务在运行**。请先执行启动命令，终端中出现 `Uvicorn running on http://127.0.0.1:8765` 后再刷新浏览器。

若报 `ModuleNotFoundError`，先执行 `pip install -r requirements.txt`，并确保安装与启动使用**同一个** Python（建议 `python3 -m pip` / `python3 -m hub`）。

---

## Hub 功能一览

| 页面 | 功能 |
|------|------|
| **LoRA 工作流** | 一键：来源目录 → 缩放/转 PNG → 输出目录 → 批量重命名（可联动 `.txt` / `.caption`） |
| **自动打标** | WD14 模型批量生成 Danbooru 风格 `.txt` caption（支持触发词） |
| **LoRA 训练** | 读取预设 TOML，调用 lora-scripts 启动 Kohya SDXL LoRA 训练 |
| 格式转换 | 多格式 → PNG；按**目标像素总面积**智能匹配 64 倍数画布（非固定输出宽高） |
| 画布填充 | 等比缩放后居中放入**自定义宽高**透明画布（输出尺寸与输入一致） |
| 区域裁剪 | 递归处理 2560×1440 PNG，固定区域裁剪并保持目录结构 |
| 尺寸筛选 | 仅保留指定宽高；先预览再删除（不可逆） |
| 批量重命名 | 前缀+补零编号 / 纯序号；支持预览；可同步标注文件 |

顶栏圆点表示依赖状态（Pillow / HEIF / natsort）。目录浏览限制在用户主目录内。

备用桌面 GUI：`python Img/image_converter.py`（tkinter，逻辑与 Hub「格式转换」相同）。

---

## LoRA 数据准备一键工作流

适用于：原始图片 → 统一尺寸 PNG → 按序重命名 → 配合 Kohya 等训练（`0001.png` + `0001.txt`）。

### 流程说明

1. **输入来源目录**：存放未处理的图片（jpg/png/webp/heic 等）
2. **选择目标宽、高**，并选择处理方式：
   - **等效面积（64 倍数）** `area_64`：目标面积 = 宽 × 高；按原图比例输出长宽均为 **64 整数倍** 的画布；**等比缩放 + 透明居中**（不拉伸）
   - **固定画布** `fixed_canvas`：输出**严格等于**所填宽 × 高；等比缩放 + 透明边补足
3. **写入输出目录**：全部保存为 PNG
4. **批量重命名**：前缀+编号（如 `0001.png`）/ 纯序号 / 跳过重命名；可选**同步重命名**同目录下的 `.txt` / `.caption`

来源目录中已有的 `.txt` / `.caption` 会**复制到输出目录**后再随图片一起重命名。

### Hub 操作

侧栏 **「LoRA 工作流」** → 填写路径与参数 → **运行完整工作流**。

### 命令行

```bash
python prepare_dataset.py \
  --source /path/to/raw_images \
  --output /path/to/dataset \
  --width 1024 --height 1024 \
  --mode area_64 \
  --digits 4 \
  --prefix ""
```

| 参数 | 说明 |
|------|------|
| `--mode area_64` | 等效面积 + 64 倍数画布（默认） |
| `--mode fixed_canvas` | 固定宽×高画布 |
| `--rename-mode` | `numbered` / `sequential` / `none` |
| `--recursive` | 递归处理子文件夹 |
| `--no-sync-captions` | 不联动重命名 txt/caption |

Python API：

```python
from img_tools.workflow import ResizeMode, WorkflowRenameOptions, RenameMode, run_prepare_workflow

run_prepare_workflow(
    "/path/raw", "/path/out",
    1024, 1024,
    ResizeMode.AREA_64,
    rename=WorkflowRenameOptions(prefix="", digits=4, sync_captions=True),
)
```

---

## WD14 自动打标

为 LoRA 训练集批量生成 Kohya 兼容的 `.txt` caption（Danbooru 风格 tag）。逻辑提取自 [lora-scripts](https://github.com/Akegarasu/lora-scripts) 的 WD14 tagger。

### Hub 操作

侧栏 **「自动打标」** → 选择图片目录 → 填写触发词 → **开始打标**。

### 命令行

```bash
python auto_tag_wd14.py --dir "C:/path/to/images" --trigger "morgana_sn" --recursive
```

| 参数 | 说明 |
|------|------|
| `--trigger` | 固定触发词，写入 caption 最前 |
| `--general-threshold` | 通用 tag 阈值（默认 0.35） |
| `--character-threshold` | 角色 tag 阈值（默认 0.1） |
| `--append` | 追加到已有 caption，不覆盖 |
| `--model` | HuggingFace 模型 repo_id |

### 内置模型（已从 lora-scripts 复制，约 361 MB）

默认模型 `wd-vit-v3` 已放在 `wd14_tagger_model/SmilingWolf_wd-vit-tagger-v3/`，**开箱即用、无需下载**（该目录已在 `.gitignore` 中，不进 Git）。

Hub 下拉框中带 **「已内置」** 的模型可直接使用；带 **「需下载」** 的会在首次使用时从 HuggingFace 自动拉取。

### 推荐 LoRA 数据流

1. **LoRA 工作流** — 图片缩放/转 PNG + 重命名  
2. **自动打标** — 生成/补充 `.txt`  
3. 手动微调 caption（可选）  
4. 送入 Kohya / lora-scripts 训练

---

## LoRA 训练（调用 lora-scripts）

无需单独打开 lora-scripts GUI，从本项目读取预设并启动训练。

### 配置文件

| 文件 | 说明 |
|------|------|
| `configs/lora/settings.toml` | lora-scripts 安装路径、CPU 线程、GPU 序号 |
| `configs/lora/morgana_star_nemesis.toml` | 训练超参预设（可复制的模板） |
| `configs/lora/runtime/` | 运行时生成的临时配置（自动生成） |
| `logs/lora_train/` | 训练日志（自动生成） |

首次使用请确认 `settings.toml` 中 `lora_scripts_root` 指向本机 lora-scripts 目录。

### Hub 操作

侧栏 **「LoRA 训练」** → 选择预设（自动填充表单）→ 修改参数 → **开始训练**。

**页面可编辑的关键参数：**

| 分组 | 参数 |
|------|------|
| 路径与输出 | 训练数据目录、底模路径、output_name、output_dir |
| 训练规模 | max_train_epochs、batch_size、save_every_n_epochs |
| LoRA 与分辨率 | 分辨率宽×高、network_dim、network_alpha |
| 学习率与 Caption | unet_lr、keep_tokens、bucket_no_upscale、full_bf16 |

修改仅作用于本次训练；切换预设会重新加载 TOML 默认值。持久修改请编辑 `configs/lora/*.toml`。

### 命令行

```bash
python train_lora.py
python train_lora.py --preset morgana_star_nemesis --train-data-dir "C:/path/to/dataset"
python train_lora.py --list-presets
```

训练在后台 subprocess 中执行，逻辑与 lora-scripts GUI 的 `/api/run` 一致（`accelerate launch` + `sdxl_train_network.py --config_file`）。

---

## 项目结构

```
AITrainScripts/
├── hub/                    # Web 入口（FastAPI + 静态前端）
│   ├── api.py
│   ├── jobs.py
│   ├── browse.py
│   ├── config.py           # HOST / PORT
│   └── static/             # index.html, app.js, styles.css
├── img_tools/              # 核心库（无 UI）
│   ├── convert.py          # 多格式转 PNG、智能面积缩放
│   ├── resize.py           # 固定画布居中填充
│   ├── crop_2k.py          # 2K 区域裁剪
│   ├── filter_2k.py        # 按尺寸筛选删除（支持 dry_run）
│   ├── rename.py           # 批量重命名、联动 caption
│   ├── tagger/             # WD14 自动打标
│   ├── lora_train/         # 调用 lora-scripts 训练
│   └── workflow.py         # LoRA 一键工作流
├── configs/lora/           # LoRA 训练预设与 settings
├── Img/                    # 独立脚本（调用 img_tools）
├── Text/xiaoshuo/          # 小说数据处理流水线
├── prepare_dataset.py      # LoRA 工作流 CLI
├── auto_tag_wd14.py        # WD14 自动打标 CLI
├── train_lora.py           # LoRA 训练 CLI
├── start_hub.py            # Hub 一键启动（跨平台）
├── start_hub.bat / .command / .sh
└── requirements.txt
```

### `img_tools` 模块说明

| 模块 | 主要 API | 说明 |
|------|----------|------|
| `convert` | `process_all` | 多格式 → PNG，`target_area` = 宽×高，64 倍数画布 |
| `resize` | `resize_png_center_batch` | 自定义宽×高透明画布 |
| `crop_2k` | `crop_2k_png_recursive` | 2560×1440 PNG 裁剪 |
| `filter_2k` | `filter_2k_images` | 保留指定尺寸，`dry_run` 预览 |
| `rename` | `batch_rename_numbered`, `rename_sequential` | 自然排序、可 `sync_captions` |
| `workflow` | `run_prepare_workflow` | 上述步骤串联 |

统一返回类型：`JobResult`（`ok`, `message`, `processed`, `errors`, `details`, `outputs`）。

### `Img/` — 图片与媒体工具

| 脚本 | 功能 |
|------|------|
| `image_converter.py` | tkinter GUI（格式转换，推荐用 Hub） |
| `crop_2k_png.py` | 2K PNG 区域裁剪 |
| `remove_non_2k_images.py` | 删除非目标尺寸图片（先预览） |
| `resize_png_center_1024.py` | 固定画布填充（薄封装） |
| `rename_images_numbered.py` | 前缀 + 补零编号 |
| `rename_images_sequential.py` | 纯序号重命名 |
| `dedupe_comma_txt_tags.py` | txt 标签去重 |
| `youtube_to_mp3.py` | YouTube 转 MP3（需 FFmpeg） |

### `Text/xiaoshuo/` — 小说数据处理

| 脚本 | 功能 |
|------|------|
| `clean_novel.py` | 清洗原始 txt |
| `create_sft_dataset.py` | 生成 SFT JSONL |
| `rag_text_chunker.py` | RAG 文本切块 |

推荐顺序：`clean_novel` → `create_sft_dataset` / `rag_text_chunker`

---

## 依赖

```bash
pip install -r requirements.txt
```

| 包 | 用途 |
|----|------|
| Pillow | 图像处理 |
| natsort | 自然排序重命名 |
| fastapi, uvicorn | Web Hub |
| pillow-heif（可选） | HEIC/HEIF 支持 |

`youtube_to_mp3.py` 另需系统安装 **FFmpeg** 与 **yt-dlp**（见脚本注释）。

---

## 更新摘要（相对初始版本）

- 抽取 **`img_tools`** 核心库，`Img/` 脚本改为薄封装
- 新增 **Web Hub**（FastAPI + Tailwind 单页，本机 `127.0.0.1:8765`）
- 新增 **LoRA 一键工作流**（Hub 页 + `prepare_dataset.py`）
- 跨平台启动：`start_hub.py` / `.bat` / `.command` / `.sh`
- 画布填充、尺寸筛选支持**自定义宽高**；重命名支持**联动 caption**
- 格式转换说明：基准宽×高为**目标面积**，非固定输出尺寸
