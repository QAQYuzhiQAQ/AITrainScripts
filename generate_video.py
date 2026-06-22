#!/usr/bin/env python3
"""
豆包 Seedance 视频生成（命令行）

使用前在项目根目录配置 .env：
  ARK_API_KEY=你的密钥

示例:
  python generate_video.py --prompt "一只金毛在麦田里奔跑，电影感镜头"
  python generate_video.py --prompt "..." --ratio 16:9 --duration 5 --output ./out.mp4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from img_tools.common import print_job_result
from video_tools.doubao_seedance import MediaReference, SeedanceRequest, run_seedance_generation
from video_tools.config import is_api_key_configured


def main() -> int:
    parser = argparse.ArgumentParser(description="豆包 Seedance 视频生成")
    parser.add_argument("--prompt", "-p", required=True, help="视频描述提示词")
    parser.add_argument("--model", default="doubao-seedance-1-5-pro-251215")
    parser.add_argument("--ratio", default="adaptive", help="画幅；图生视频推荐 adaptive")
    parser.add_argument("--resolution", default="480p", help="输出分辨率：480p / 720p / 1080p")
    parser.add_argument("--duration", type=int, default=5, help="秒；图生视频仅 5/10/15")
    parser.add_argument("--no-audio", action="store_true", help="不生成音频")
    parser.add_argument("--watermark", action="store_true")
    parser.add_argument("--output", "-o", help="下载保存路径（.mp4）")
    parser.add_argument(
        "--refs",
        help='JSON 参考素材，如 \'[{"type":"image_url","url":"https://...","role":"reference_image"}]\'',
    )
    args = parser.parse_args()

    if not is_api_key_configured():
        print("错误: 未配置 ARK_API_KEY。请复制 .env.example 为 .env 并填入密钥。")
        return 1

    references: list[MediaReference] = []
    if args.refs:
        for item in json.loads(args.refs):
            references.append(
                MediaReference(
                    type=item["type"],
                    url=item["url"],
                    role=item.get("role"),
                )
            )

    req = SeedanceRequest(
        prompt=args.prompt,
        references=references,
        model=args.model,
        ratio=args.ratio,
        resolution=args.resolution,
        duration=args.duration,
        generate_audio=not args.no_audio,
        watermark=args.watermark,
    )

    result = run_seedance_generation(req, output_path=args.output)
    print_job_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
