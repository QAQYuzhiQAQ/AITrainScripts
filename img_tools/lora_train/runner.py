"""
通过 subprocess 调用 lora-scripts（Kohya）训练脚本。

与 lora-scripts GUI `/api/run` 行为一致：读取 TOML → accelerate launch → train_network.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from img_tools.common import JobResult, ensure_dir
from img_tools.lora_train.progress import TrainProgress, parse_train_line

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs" / "lora"
SETTINGS_FILE = CONFIG_DIR / "settings.toml"
RUNTIME_DIR = CONFIG_DIR / "runtime"
LOG_DIR = PROJECT_ROOT / "logs" / "lora_train"

TRAINER_MAPPING: dict[str, str] = {
    "sd-lora": "scripts/stable/train_network.py",
    "sdxl-lora": "scripts/stable/sdxl_train_network.py",
    "sd-dreambooth": "scripts/stable/train_db.py",
    "sdxl-finetune": "scripts/stable/sdxl_train.py",
    "sd3-lora": "scripts/dev/sd3_train_network.py",
    "flux-lora": "scripts/dev/flux_train_network.py",
    "flux-finetune": "scripts/dev/flux_train.py",
}

# 简单 TOML 解析（仅支持 flat key = value，足够读取本项目配置）
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


def _dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, val in data.items():
        if isinstance(val, bool):
            s = "true" if val else "false"
        elif isinstance(val, (int, float)):
            s = str(val)
        else:
            s = f'"{val}"'
        lines.append(f"{key} = {s}")
    return "\n".join(lines) + "\n"


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.is_file():
        return {
            "lora_scripts_root": "",
            "cpu_threads": 8,
            "gpu_ids": "",
        }
    return _parse_toml(SETTINGS_FILE)


def list_presets() -> list[dict[str, str]]:
    presets: list[dict[str, str]] = []
    if not CONFIG_DIR.is_dir():
        return presets
    for path in sorted(CONFIG_DIR.glob("*.toml")):
        if path.name == "settings.toml":
            continue
        presets.append({"id": path.stem, "name": path.stem, "path": str(path)})
    return presets


def load_preset_config(preset: str) -> dict[str, Any]:
    """读取预设 TOML 为字典（含 model_train_type）。"""
    preset_path = CONFIG_DIR / f"{preset}.toml"
    if not preset_path.is_file():
        raise FileNotFoundError(f"预设不存在: {preset}")
    return _parse_toml(preset_path)


def _resolve_python(lora_root: Path) -> Path:
    candidates = [
        lora_root / "venv" / "Scripts" / "python.exe",
        lora_root / "python" / "python.exe",
    ]
    for exe in candidates:
        if exe.is_file():
            return exe
    return Path(sys.executable)


def _validate_before_train(config: dict[str, Any], lora_root: Path) -> str | None:
    if not lora_root.is_dir():
        return f"lora-scripts 路径不存在: {lora_root}"

    train_dir = Path(str(config.get("train_data_dir", "")))
    if not train_dir.is_dir():
        return f"训练数据目录不存在: {train_dir}"

    model_path = Path(str(config.get("pretrained_model_name_or_path", "")))
    if not model_path.is_file():
        return f"底模文件不存在: {model_path}"

    train_type = config.get("model_train_type", "sdxl-lora")
    if train_type not in TRAINER_MAPPING:
        return f"不支持的 model_train_type: {train_type}"

    trainer = lora_root / TRAINER_MAPPING[train_type]
    if not trainer.is_file():
        return f"训练脚本不存在: {trainer}"

    return None


def run_lora_train(
    preset: str = "morgana_star_nemesis",
    *,
    overrides: dict[str, Any] | None = None,
    progress_callback: Callable[[dict[str, Any], str], None] | None = None,
) -> JobResult:
    """
    加载预设 TOML，写入 runtime 配置，在 lora-scripts 目录下启动训练 subprocess。
    """
    preset_path = CONFIG_DIR / f"{preset}.toml"
    if not preset_path.is_file():
        return JobResult(ok=False, message=f"预设不存在: {preset}")

    settings = load_settings()
    lora_root = Path(str(settings.get("lora_scripts_root", ""))).resolve()
    cpu_threads = int(settings.get("cpu_threads", 8))
    gpu_ids = str(settings.get("gpu_ids", "")).strip()

    config = _parse_toml(preset_path)
    if overrides:
        config.update({k: v for k, v in overrides.items() if v is not None and v != ""})

    train_type = str(config.pop("model_train_type", "sdxl-lora"))
    max_epochs = int(config.get("max_train_epochs", 10) or 10)
    err = _validate_before_train({**config, "model_train_type": train_type}, lora_root)
    if err:
        return JobResult(ok=False, message=err)

    ensure_dir(RUNTIME_DIR)
    ensure_dir(LOG_DIR)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    runtime_toml = RUNTIME_DIR / f"{preset}_{ts}.toml"
    log_file = LOG_DIR / f"{preset}_{ts}.log"

    runtime_toml.write_text(_dump_toml(config), encoding="utf-8")

    python_exe = _resolve_python(lora_root)
    trainer_rel = TRAINER_MAPPING[train_type]
    trainer_file = str(lora_root / trainer_rel)

    cmd = [
        str(python_exe),
        "-m",
        "accelerate.commands.launch",
        "--num_cpu_threads_per_process",
        str(cpu_threads),
        "--quiet",
        trainer_file,
        "--config_file",
        str(runtime_toml.resolve()),
    ]

    env = os.environ.copy()
    env["HF_HOME"] = str(lora_root / "huggingface")
    env["XFORMERS_FORCE_DISABLE_TRITON"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["ACCELERATE_DISABLE_RICH"] = "1"
    env["PYTHONWARNINGS"] = "ignore::FutureWarning,ignore::UserWarning"
    if gpu_ids:
        env["CUDA_VISIBLE_DEVICES"] = gpu_ids

    details = [
        f"预设: {preset}",
        f"lora-scripts: {lora_root}",
        f"训练类型: {train_type}",
        f"配置文件: {runtime_toml}",
        f"日志文件: {log_file}",
        f"命令: {' '.join(cmd)}",
        "--- 训练输出 ---",
    ]

    progress_state = TrainProgress(max_epochs=max_epochs, status="starting", message="正在启动训练…")
    if progress_callback:
        progress_callback(progress_state.to_dict(), "正在启动训练进程…")

    try:
        with log_file.open("w", encoding="utf-8") as log_fp:
            log_fp.write(f"Command: {' '.join(cmd)}\n\n")
            log_fp.flush()

            proc = subprocess.Popen(
                cmd,
                cwd=str(lora_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert proc.stdout is not None
            for line in proc.stdout:
                log_fp.write(line)
                log_fp.flush()
                progress_state = parse_train_line(line, progress_state)
                if progress_state.max_epochs == 0 and max_epochs:
                    progress_state.max_epochs = max_epochs
                if progress_callback:
                    progress_callback(progress_state.to_dict(), line.rstrip("\n"))

            return_code = proc.wait()
        tail = _read_log_tail(log_file, 80)
        details.extend(tail)

        if return_code != 0:
            return JobResult(
                ok=False,
                message=f"训练失败，退出码 {return_code}（详见日志）",
                errors=[f"exit code {return_code}"],
                details=details,
                outputs=[log_file, runtime_toml],
            )

        return JobResult(
            ok=True,
            message=f"训练完成：{config.get('output_name', preset)}",
            processed=1,
            details=details,
            outputs=[log_file, runtime_toml, Path(str(config.get("output_dir", "")))],
        )
    except Exception as e:
        return JobResult(
            ok=False,
            message=f"启动训练失败: {e}",
            errors=[str(e)],
            details=details,
            outputs=[log_file] if log_file.exists() else [],
        )


def _read_log_tail(path: Path, lines: int) -> list[str]:
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return content[-lines:]
