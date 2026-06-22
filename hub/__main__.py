"""启动 Hub：python -m hub"""

import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _open_browser_when_ready(url: str, timeout: float = 15.0) -> None:
    """等服务就绪后再用系统默认浏览器打开页面。"""

    def _worker() -> None:
        health_url = f"{url}/api/health"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(health_url, timeout=1):
                    webbrowser.open(url)
                    return
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.25)
        webbrowser.open(url)

    threading.Thread(target=_worker, daemon=True).start()


def main() -> None:
    import uvicorn

    from hub.config import HOST, PORT

    url = f"http://{HOST}:{PORT}"
    print(f"\n  AITrainScripts Hub 已启动 → 正在打开浏览器: {url}\n  按 Ctrl+C 停止服务\n")

    _open_browser_when_ready(url)

    uvicorn.run(
        "hub.api:app",
        host=HOST,
        port=PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
