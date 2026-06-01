"""将仓库根目录加入 sys.path，便于从 Img/ 子目录运行脚本。"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def ensure_repo_on_path() -> Path:
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return _REPO_ROOT
