"""豆包 / 火山方舟 API 配置（密钥从环境变量或 .env 读取）。"""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_LOADED = False


def _load_dotenv() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_path = _REPO_ROOT / ".env"
    if env_path.is_file():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _ENV_LOADED = True


def get_api_key() -> str | None:
    """读取 ARK_API_KEY（或 DOUBAO_API_KEY）。未配置时返回 None。"""
    _load_dotenv()
    return os.environ.get("ARK_API_KEY") or os.environ.get("DOUBAO_API_KEY") or None


def is_api_key_configured() -> bool:
    key = get_api_key()
    return bool(key and key.strip() and "YOUR_API_KEY" not in key)
