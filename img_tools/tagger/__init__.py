"""WD14 等自动打标模块（逻辑源自 lora-scripts / Kohya wd14 tagger）。"""

from img_tools.tagger.wd14 import WD14_MODELS, WD14TagOptions, tag_images_wd14

__all__ = ["WD14_MODELS", "WD14TagOptions", "tag_images_wd14"]
