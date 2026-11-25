from app.services import alerts
from app.services.alerts import build_alerts

BASE = {"date": "2026-11-16", "precipitation": 0, "temp_min": 8, "temp_max": 14, "feels_like": 10, "hourly": []}


def _ids(a):
    return {x["id"] for x in a}


def test_umbrella_when_rain_expected():
    w = {**BASE, "hourly": [{"time": "2026-11-16T15:00", "hour": 15, "pop": 80, "precip": 0.2}]}
    assert "umbrella" in _ids(build_alerts(w, None, None))


def test_no_umbrella_when_dry():
    w = {**BASE, "hourly": [{"time": "2026-11-16T15:00", "hour": 15, "pop": 10, "precip": 0}]}
    assert "umbrella" not in _ids(build_alerts(w, None, None))


def test_temperature_swing_alert():
    w = {**BASE, "temp_min": 3, "temp_max": 15}
    assert "swing" in _ids(build_alerts(w, None, None))


def test_bad_dust_and_dry_room():
    got = _ids(build_alerts(None, {"pm25_grade": "나쁨"}, {"humidity": 22}))
    assert {"dust", "dry"} <= got


class FakeHub:
    def __init__(self):
        self.sent = []

    def send(self, cmd):
        self.sent.append(cmd)


def test_arduino_notified_once_per_rain():
    hub, rain = FakeHub(), [{"id": "umbrella"}]
    alerts._umbrella_notified = False
    alerts.maybe_notify_arduino(rain, presence=False, hub=hub)   # 사람 없음 → 울리지 않음
    alerts.maybe_notify_arduino(rain, presence=True, hub=hub)    # 사람 등장 → 1회
    alerts.maybe_notify_arduino(rain, presence=True, hub=hub)    # 중복 없음
    assert hub.sent == ["ALERT"]
    alerts.maybe_notify_arduino([], presence=True, hub=hub)      # 비 예보 해제 → 초기화
    alerts.maybe_notify_arduino(rain, presence=True, hub=hub)
    assert hub.sent == ["ALERT", "ALERT"]
