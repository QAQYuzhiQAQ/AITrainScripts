# =============================================================================
# 脚本名称: main.py
# 功能描述: Img 目录脚本索引（本文件不执行具体任务，仅作导航参考）
#
# 可用脚本一览:
#   crop_2k_png.py              - 裁剪 2560×1440 PNG 到指定区域
#   image_converter.py          - GUI 图片格式转换与智能缩放（逻辑在 img_tools）
#   核心库 img_tools/           - 业务逻辑
#   Web Hub: python -m hub       - 推荐统一入口 http://127.0.0.1:8765
#   remove_non_2k_images.py     - 删除非 2K 尺寸的图片
#   resize_png_center_1024.py   - PNG 缩放并居中填充至 1024×1024
#   rename_images_numbered.py   - 图片批量重命名（前缀+补零编号）
#   rename_images_sequential.py - 图片批量重命名（纯序号）
#   dedupe_comma_txt_tags.py    - 逗号分隔 txt 标签去重与过滤
#   youtube_to_mp3.py           - YouTube 视频批量转 MP3
#
# 根目录 CLI / Hub:
#   auto_tag_wd14.py              - WD14 自动打标（LoRA caption）
#   convert_format.py             - 图片格式互转（保持尺寸）
#   rename_subfolders.py           - 子文件夹重命名（10_ 前缀 + 去空格）
#   make_ico.py                   - PNG/JPG 等转 Windows ICO
#   prepare_dataset.py            - LoRA 数据准备工作流（旧版分步）
#   run_lora_pipeline.py          - LoRA 完整流程（8 步一键）
#   python -m hub                 - Web Hub（含自动打标页面）
# =============================================================================

if __name__ == '__main__':
    print('请直接运行对应的功能脚本，例如: python image_converter.py')
