"""미러 화면과 LLM 이 함께 쓰는 '현재 상황' 한 덩어리를 조립한다."""
import datetime as dt
from zoneinfo import ZoneInfo

from ..config import settings
from ..database import list_clothes, list_todos
from ..utils import safe
from .alerts import build_alerts
from .calendar_service import today_events
from .outfit import recommend
from .sensors import sensor_hub
from .weather import get_air_quality, get_weather

WEEKDAYS = "월화수목금토일"


def build_context() -> dict:
    """각 파트는 독립적으로 실패할 수 있다. (예: 와이파이 불량 → weather=None 이어도 시계/센서는 표시)"""
    weather = safe(get_weather)
    air = safe(get_air_quality)
    indoor = sensor_hub.snapshot()
    calendar = safe(today_events) or {"source": "error", "events": []}
    outfit = safe(lambda: recommend(weather)) if weather else None
    return {
        "weather": weather,
        "air": air,
        "indoor": indoor,
        "events": calendar["events"],
        "events_source": calendar["source"],
        "todos": list_todos(),
        "outfit": outfit,
        "alerts": build_alerts(weather, air, indoor),
    }


def llm_view(ctx: dict) -> dict:
    """LLM 에 줄 요약본 (이미지 URL 같은 불필요한 정보는 뺀다)."""
    now = dt.datetime.now(ZoneInfo(settings.timezone))
    w, indoor, air = ctx["weather"], ctx["indoor"], ctx["air"]
    names = lambda item: item["name"] if item else None  # noqa: E731

    return {
        "now": now.strftime(f"%Y-%m-%d %H:%M ({WEEKDAYS[now.weekday()]}요일)"),
        "weather": {k: w[k] for k in ("summary", "temp", "feels_like", "temp_min", "temp_max", "rain_prob_max", "humidity")} if w else None,
        "indoor": {k: indoor.get(k) for k in ("temp", "humidity", "discomfort_label")},
        "air": {"pm25_grade": air["pm25_grade"], "pm10_grade": air["pm10_grade"]} if air else None,
        "events": [{"start": e["start"], "end": e["end"], "title": e["title"]} for e in ctx["events"]],
        "todos": [t["text"] for t in ctx["todos"] if not t["done"]],
        "recommended_outfits": [
            {"top": names(c["top"]), "bottom": names(c["bottom"]), "outer": names(c["outer"]), "reasons": c["reasons"]}
            for c in (ctx["outfit"] or {}).get("candidates", [])
        ],
        "wardrobe": [
            {"name": c["name"], "category": c["category"], "color": c["color"], "warmth": c["warmth"], "waterproof": c["waterproof"]}
            for c in list_clothes()[:60]
        ],
        "alerts": [a["message"] for a in ctx["alerts"]],
    }
