"""Seedance 视频时长校验（不同生成模式限制不同）。"""

from __future__ import annotations

from typing import Literal, Protocol

GenerationMode = Literal["t2v", "i2v", "multimodal"]


class _RefLike(Protocol):
    type: str
    url: str

I2V_DURATIONS = (5, 10, 15)
MIN_DURATION = 4
MAX_DURATION = 15


def detect_generation_mode(references: list[_RefLike]) -> GenerationMode:
    """根据参考素材推断 API 生成模式。"""
    active = [r for r in references if r.url.strip()]
    if not active:
        return "t2v"
    if any(r.type in ("video_url", "audio_url") for r in active):
        return "multimodal"
    if any(r.type == "image_url" for r in active):
        return "i2v"
    return "t2v"


def duration_hint(mode: GenerationMode) -> str:
    if mode == "i2v":
        return "图生视频仅支持 5 / 10 / 15 秒"
    return "支持 4–15 秒（整数）"


def validate_duration(duration: int, mode: GenerationMode) -> int:
    """校验时长；不合法时抛出 ValueError（中文说明）。"""
    if duration == -1:
        return -1

    if mode == "i2v":
        if duration not in I2V_DURATIONS:
            allowed = "、".join(str(d) for d in I2V_DURATIONS)
            raise ValueError(
                f"图生视频模式下时长仅支持 {allowed} 秒（当前为 {duration} 秒）。"
                "请改用上述取值。"
            )
        return duration

    if not MIN_DURATION <= duration <= MAX_DURATION:
        raise ValueError(
            f"时长须在 {MIN_DURATION}–{MAX_DURATION} 秒之间（当前为 {duration} 秒）。"
        )
    return duration
