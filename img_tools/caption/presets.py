"""Caption 清洗 / 打标预设加载。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs" / "caption"

_TOML_LINE = re.compile(
    r"^\s*(?P<key>[A-Za-z0-9_]+)\s*=\s*(?P<val>.+?)\s*(?:#.*)?$"
)


def _parse_toml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        m = _TOML_LINE.match(line)
        if not m:
            continue
        key, raw = m.group("key"), m.group("val")
        data[key] = _parse_toml_value(raw)
    return data


def _parse_toml_value(raw: str) -> Any:
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"')
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        if "." in raw or "e" in lower:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def list_presets() -> list[dict[str, str]]:
    if not CONFIG_DIR.is_dir():
        return []
    items: list[dict[str, str]] = []
    for path in sorted(CONFIG_DIR.glob("*.toml")):
        cfg = _parse_toml(path)
        items.append({
            "id": path.stem,
            "name": str(cfg.get("name") or path.stem),
        })
    return items


def load_preset(preset_id: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{preset_id}.toml"
    if not path.is_file():
        raise FileNotFoundError(f"Caption 预设不存在: {preset_id}")
    return _parse_toml(path)


def parse_tag_list(raw: str | None, separator: str = ",") -> list[str]:
    if not raw:
        return []
    sep = separator.strip() or ","
    parts = raw.split(sep) if sep in raw else raw.split(",")
    return [p.strip() for p in parts if p.strip()]


def parse_mutual_exclude(raw: str | None) -> list[tuple[str, list[str]]]:
    """解析 mutual_exclude: 'red_hair:brown_hair|pink_hair, blue_hair:green_hair'"""
    if not raw:
        return []
    rules: list[tuple[str, list[str]]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        when, removes = chunk.split(":", 1)
        when = when.strip()
        remove_list = [r.strip() for r in removes.split("|") if r.strip()]
        if when and remove_list:
            rules.append((when, remove_list))
    return rules
