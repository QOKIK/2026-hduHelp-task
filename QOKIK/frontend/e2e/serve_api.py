import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import uvicorn

from app.main import create_app


app = create_app(
    os.environ["HDUHELP_DB"],
    os.environ["HDUHELP_ADMIN_USERNAME"],
    os.environ["HDUHELP_ADMIN_PASSWORD"],
)
uvicorn.run(app, host="127.0.0.1", port=8001)
