"""py -3.11 -m server  ->  starts Video Clipper on http://127.0.0.1:8000 (this computer only) and opens it.

Options:  --no-browser   do not open the browser      PORT=9000   use another port
"""
import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn


def open_when_ready(url):
    for _ in range(60):
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    webbrowser.open(url)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    url = f"http://127.0.0.1:{port}"
    if not (Path(__file__).resolve().parent.parent / "webui" / "index.html").exists():
        print("The web interface files (webui/) are missing. Build them once with:  cd frontend && npm install && npm run build")
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    print(f"\nVideo Clipper is running at {url}\nLeave this window open while you use it. Press Ctrl+C to stop.\n")
    uvicorn.run("server.main:app", host="127.0.0.1", port=port, log_level="warning")
