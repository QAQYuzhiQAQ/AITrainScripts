"""音频处理工具。"""

from audio_tools.mp4_to_mp3 import is_ffmpeg_available, mp4_to_mp3_batch

__all__ = ["is_ffmpeg_available", "mp4_to_mp3_batch"]
