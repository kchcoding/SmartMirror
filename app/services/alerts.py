"""알림 규칙: 우산 / 일교차 / 미세먼지 / 실내 습도 / 극한 기온.

build_alerts() 는 순수 함수라서 테스트하기 쉽다. (tests/test_alerts.py 참고)
"""
from ..config import settings


def _umbrella(weather: dict) -> dict | None:
    if weather.get("precipitation", 0) > 0:
        return _alert("umbrella", "warning", "☂️", "지금 비가 오고 있어요. 우산을 챙기세요!")

    today = weather.get("date")
    for h in weather.get("hourly", []):
        if h["pop"] >= settings.rain_prob_threshold or h["precip"] > 0:
            day = "" if h["time"][:10] == today else "내일 "
            return _alert(
                "umbrella", "warning", "☂️",
                f"{day}{h['hour']}시경 비 예보 (강수확률 {h['pop']}%). 우산 챙기세요!",
            )
    return None


def _alert(id_: str, level: str, icon: str, message: str) -> dict:
    return {"id": id_, "level": level, "icon": icon, "message": message}


def build_alerts(weather: dict | None, air: dict | None, indoor: dict | None) -> list[dict]:
    alerts: list[dict] = []

    if weather:
        if (a := _umbrella(weather)):
            alerts.append(a)

        swing = weather["temp_max"] - weather["temp_min"]
        if swing >= 10:
            alerts.append(_alert("swing", "info", "🧥", f"일교차가 {swing:.0f}°C예요. 겉옷을 챙기세요."))

        fl = weather["feels_like"]
        if fl >= 33:
            alerts.append(_alert("heat", "warning", "🥵", f"체감 {fl:.0f}°C 폭염이에요. 물을 자주 마시세요."))
        elif fl <= -5:
            alerts.append(_alert("cold", "warning", "🥶", f"체감 {fl:.0f}°C 한파예요. 따뜻하게 입으세요."))

    if air and air.get("pm25_grade") in ("나쁨", "매우나쁨"):
        alerts.append(_alert("dust", "warning", "😷", f"초미세먼지 {air['pm25_grade']}. 마스크를 챙기세요."))

    if indoor and indoor.get("humidity") is not None:
        hum = indoor["humidity"]
        if hum < 30:
            alerts.append(_alert("dry", "info", "💧", f"실내 습도 {hum:.0f}%로 건조해요. 가습을 추천해요."))
        elif hum > 70:
            alerts.append(_alert("humid", "info", "💦", f"실내 습도 {hum:.0f}%로 습해요. 환기를 추천해요."))

    return alerts


# ── 아두이노 버저/LED 알림 (같은 비 예보로 계속 울리지 않도록 상태를 기억) ──
_umbrella_notified = False


def maybe_notify_arduino(alerts: list[dict], presence: bool, hub) -> None:
    """우산 알림이 있고 + 사람이 앞에 있을 때 + 아직 안 울렸으면 1번 울린다."""
    global _umbrella_notified
    has_umbrella = any(a["id"] == "umbrella" for a in alerts)
    if not has_umbrella:
        _umbrella_notified = False  # 비 예보가 사라지면 다음 비를 위해 초기화
        return
    if presence and not _umbrella_notified:
        hub.send("ALERT")
        _umbrella_notified = True
