"""启动 Hub：python -m hub"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> None:
    import uvicorn

    from hub.config import HOST, PORT

    url = f"http://{HOST}:{PORT}"
    print(f"\n  AITrainScripts Hub 已启动 → 在浏览器打开: {url}\n  按 Ctrl+C 停止服务\n")

    uvicorn.run(
        "hub.api:app",
        host=HOST,
        port=PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
