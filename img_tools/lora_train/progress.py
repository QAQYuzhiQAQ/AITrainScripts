"""从 Kohya 训练日志解析进度信息。"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

_EPOCH = re.compile(r"epoch\s+(\d+)\s*/\s*(\d+)", re.I)
_TQDM_STEP = re.compile(r"\|\s*(\d+)\s*/\s*(\d+)\s*\[")
_AVR_LOSS = re.compile(r"avr_loss=([\d.eE+-]+)")
_LOSS = re.compile(r"\bloss[=:\s]+([\d.eE+-]+)", re.I)


@dataclass
class TrainProgress:
    epoch: int = 0
    max_epochs: int = 0
    step: int = 0
    max_steps: int = 0
    loss: float | None = None
    percent: float = 0.0
    status: str = "starting"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_train_line(line: str, state: TrainProgress) -> TrainProgress:
    """解析单行日志，更新并返回进度状态。"""
    text = line.strip()
    if not text:
        return state

    m = _EPOCH.search(text)
    if m:
        state.epoch = int(m.group(1))
        state.max_epochs = int(m.group(2))
        state.status = "training"
        state.message = f"Epoch {state.epoch}/{state.max_epochs}"

    m = _TQDM_STEP.search(text)
    if m:
        state.step = int(m.group(1))
        state.max_steps = int(m.group(2))
        if state.max_steps > 0:
            state.percent = round(state.step / state.max_steps * 100, 1)

    m = _AVR_LOSS.search(text) or _LOSS.search(text)
    if m:
        try:
            state.loss = float(m.group(1))
        except ValueError:
            pass

    if state.max_epochs > 0 and state.epoch > 0:
        epoch_pct = (state.epoch - 1) / state.max_epochs
        step_pct = (state.step / state.max_steps) if state.max_steps > 0 else 0
        state.percent = round(min(99.9, (epoch_pct + step_pct / state.max_epochs) * 100), 1)

    if "Training finished" in text or "训练完成" in text:
        state.status = "completed"
        state.percent = 100.0
        state.message = "训练完成"

    state.message = state.message or text[:120]
    return state
