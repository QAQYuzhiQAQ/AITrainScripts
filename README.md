# AITrainScripts

个人 AI 训练与数据处理脚本集合。

## 目录结构

### `Img/` — 图片与媒体工具

| 脚本 | 功能 |
|---|---|
| `image_converter.py` | GUI 图片格式转换、智能缩放、批量重命名 |
| `crop_2k_png.py` | 裁剪 2560×1440 PNG 到指定区域 |
| `remove_non_2k_images.py` | 删除非 2K 尺寸的图片 |
| `resize_png_center_1024.py` | PNG 缩放并居中填充至 1024×1024 |
| `rename_images_numbered.py` | 图片批量重命名（前缀+补零编号） |
| `rename_images_sequential.py` | 图片批量重命名（纯序号） |
| `dedupe_comma_txt_tags.py` | 逗号分隔 txt 标签去重与过滤 |
| `youtube_to_mp3.py` | YouTube 视频批量转 MP3 |

### `Text/xiaoshuo/` — 小说 AI 数据处理流水线

| 脚本 | 功能 |
|---|---|
| `clean_novel.py` | 清洗原始小说 txt |
| `create_sft_dataset.py` | 生成 SFT 微调训练集（JSONL） |
| `rag_text_chunker.py` | 文本切块，供 RAG 向量检索使用 |

推荐处理顺序：`clean_novel` → `create_sft_dataset` / `rag_text_chunker`

## 依赖

各脚本头部注释中标注了所需依赖，常见库：

```bash
pip install Pillow natsort yt-dlp
```
