"""`py -m server` really starts and serves the interface and the API."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_python_dash_m_server_serves_the_app(tmp_path):
    port = "8765"
    env = {**os.environ, "PORT": port, "CLIPPER_DATA_DIR": str(tmp_path / "data")}
    proc = subprocess.Popen([sys.executable, "-m", "server", "--no-browser"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                if b"ok" in urllib.request.urlopen(url + "/api/health", timeout=1).read():
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("server did not start")
        page = urllib.request.urlopen(url + "/").read().decode()
        assert "<title>Video Clipper</title>" in page and '<div id="root">' in page  # the React app
        assert urllib.request.urlopen(url + "/jobs/anything").status == 200      # page refresh on a deep link
    finally:
        proc.terminate()
        proc.wait(timeout=10)
