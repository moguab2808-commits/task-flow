import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.staticfiles import StaticFiles
from app.main import app as taskflow

# 라우터가 이미 /api 접두사를 가지고 있으므로 다시 마운트하지 않고 그대로 쓴다.
app = taskflow
app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True))