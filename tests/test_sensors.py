import time

from app.config import settings
from app.services.sensors import SensorHub


def _stale(hub):
    hub._last_motion = time.time() - 9999   # '오래전에 마지막 감지' 상태로 만들기


def test_parses_dht_and_distance():
    hub = SensorHub()
    hub._handle_line('{"t":23.0,"h":45.0,"d":87}')
    snap = hub.snapshot()
    assert snap["temp"] == 23.0 and snap["humidity"] == 45.0


def test_person_in_range_means_presence():
    hub = SensorHub(); _stale(hub)
    assert hub.snapshot()["presence"] is False
    hub._handle_line('{"t":23.0,"h":45.0,"d":80}')
    assert hub.snapshot()["presence"] is True


def test_far_object_is_not_presence():
    hub = SensorHub(); _stale(hub)
    hub._handle_line(f'{{"d":{settings.presence_distance_cm + 50}}}')
    assert hub.snapshot()["presence"] is False


def test_ignores_garbage_lines():
    hub = SensorHub()
    hub._handle_line("booting...")
    hub._handle_line('{"ok":1}')
    assert hub.snapshot()["temp"] is None
