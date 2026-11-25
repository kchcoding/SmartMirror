"""미러 화면이 주기적으로 호출하는 통합 상태 API."""
from fastapi import APIRouter

from ..services.alerts import maybe_notify_arduino
from ..services.context import build_context
from ..services.sensors import sensor_hub

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/state")
def get_state():
    """날씨·대기질·실내환경·일정·할 일·코디·알림을 한 번에 돌려준다."""
    ctx = build_context()
    maybe_notify_arduino(ctx["alerts"], ctx["indoor"]["presence"], sensor_hub)
    return ctx
