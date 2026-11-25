"""Smart Mirror 서버 진입점.

실행:  uvicorn app.main:app --host 0.0.0.0 --port 8000
  - 미러 화면:   http://localhost:8000/
  - 관리(폰):    http://<라즈베리파이 IP>:8000/admin.html
  - API 문서:    http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR
from .database import WARDROBE_DIR, init_db
from .routers import assistant, dashboard, todos, tryon, wardrobe
from .services.sensors import sensor_hub
from .services.tryon import tryon_engine

init_db()  # StaticFiles 가 폴더 존재를 요구하므로 import 시점에 보장


@asynccontextmanager
async def lifespan(app: FastAPI):
    sensor_hub.start()   # 아두이노 읽기 스레드
    tryon_engine.start() # 카메라 스레드 (TRYON_ENABLED=true 일 때만)
    yield


app = FastAPI(title="Smart Mirror", lifespan=lifespan)

for r in (dashboard, wardrobe, todos, tryon, assistant):
    app.include_router(r.router)

# 순서 중요: 구체적인 경로를 먼저, 전체("/")는 마지막에
app.mount("/data/wardrobe", StaticFiles(directory=WARDROBE_DIR), name="wardrobe-images")
app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
