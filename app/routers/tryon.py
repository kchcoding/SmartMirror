"""가상 시착 API: 카메라 스트림 + 어떤 코디를 입혀볼지 선택."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.tryon import tryon_engine

router = APIRouter(prefix="/api/tryon", tags=["tryon"])


class Selection(BaseModel):
    top: int | None = None
    bottom: int | None = None
    outer: int | None = None


@router.get("/status")
def status():
    return tryon_engine.status()


@router.post("/select")
def select(body: Selection):
    tryon_engine.set_selection(body.model_dump())
    return tryon_engine.status()


@router.get("/stream")
def stream():
    if not tryon_engine.available:
        raise HTTPException(status_code=503, detail=tryon_engine.error or "시착 엔진 준비 중")
    return StreamingResponse(tryon_engine.mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")
