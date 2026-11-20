"""py -3.11 -m server   ->  starts the app on http://127.0.0.1:8000 (this computer only)."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), log_level="info")
