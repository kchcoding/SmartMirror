"""오늘의 일정.

구글 캘린더의 '비공개 iCal 주소(.ics)'를 읽는 방식이라 OAuth 로그인이 필요 없습니다.
(라즈베리파이처럼 화면/키보드 없는 기기에서 훨씬 편함)

주소 얻는 법: 구글 캘린더 웹 → 내 캘린더 설정 → '비공개 주소(iCal 형식)' 복사 → .env 의 ICS_URL
ICS_URL 이 비어 있으면 데모 일정을 보여줍니다.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import httpx

from ..config import settings
from ..utils import ttl_cache

DEMO_EVENTS = [
    {"title": "임베디드시스템 팀 회의", "start": "14:00", "end": "15:00", "location": "S06-604", "all_day": False},
    {"title": "딥러닝 과제 제출", "start": "23:59", "end": "23:59", "location": "", "all_day": False},
]


@ttl_cache(300)  # 5분마다 갱신
def today_events() -> dict:
    if not settings.ics_url:
        return {"source": "demo", "events": DEMO_EVENTS}
    return {"source": "ics", "events": _fetch_ics_events()}


def _localize(value, tz):
    """naive datetime 이면 로컬 타임존을 붙이고, aware 이면 로컬로 변환."""
    return value.astimezone(tz) if value.tzinfo else value.replace(tzinfo=tz)


def _fetch_ics_events() -> list[dict]:
    import icalendar
    import recurring_ical_events

    tz = ZoneInfo(settings.timezone)
    resp = httpx.get(settings.ics_url, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    cal = icalendar.Calendar.from_ical(resp.content)

    today = dt.datetime.now(tz).date()
    start = dt.datetime.combine(today, dt.time.min, tzinfo=tz)
    end = start + dt.timedelta(days=1)

    events = []
    for ev in recurring_ical_events.of(cal).between(start, end):  # 반복 일정도 펼쳐줌
        s = ev["DTSTART"].dt
        e = ev["DTEND"].dt if "DTEND" in ev else s
        all_day = not isinstance(s, dt.datetime)  # datetime 은 date 의 하위 클래스라 순서 주의
        events.append(
            {
                "title": str(ev.get("SUMMARY", "(제목 없음)")),
                "start": "종일" if all_day else _localize(s, tz).strftime("%H:%M"),
                "end": "" if all_day else _localize(e, tz).strftime("%H:%M"),
                "location": str(ev.get("LOCATION", "")),
                "all_day": all_day,
            }
        )
    events.sort(key=lambda x: "00:00" if x["all_day"] else x["start"])
    return events
