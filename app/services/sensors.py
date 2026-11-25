"""아두이노 센서 허브.

아두이노가 USB 시리얼로 2초마다 보내는 JSON 한 줄을 읽어서 최신값을 들고 있는다.
    {"t": 23.0, "h": 45.0, "d": 87}     # d = 가장 가까웠던 거리(cm), 없으면 생략
반대로 라즈베리파이 → 아두이노 명령도 보낼 수 있다. (예: "ALERT" → 버저+LED)

SENSOR_MODE=mock 이면 아두이노 없이도 가짜 데이터가 나온다. (노트북 개발용)
"""
import json
import math
import random
import threading
import time

from ..config import settings
from ..utils import log


def discomfort_index(temp_c: float, humidity: float) -> float:
    """불쾌지수 (온도 + 습도로 사람이 느끼는 답답함을 수치화)."""
    return 0.81 * temp_c + 0.01 * humidity * (0.99 * temp_c - 14.3) + 46.3


def discomfort_label(di: float) -> str:
    if di >= 80:
        return "매우 높음"
    if di >= 75:
        return "높음"
    if di >= 68:
        return "보통"
    return "낮음"


def humidity_label(h: float) -> str:
    if h < 30:
        return "건조"
    if h > 70:
        return "습함"
    return "쾌적"


class SensorHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._temp: float | None = None
        self._humidity: float | None = None
        self._last_update = 0.0
        self._last_motion = time.time()
        self._ser = None

    # ── 시작 ──
    def start(self) -> None:
        target = self._run_serial if settings.sensor_mode == "serial" else self._run_mock
        threading.Thread(target=target, daemon=True, name="sensor-hub").start()
        log.info("센서 허브 시작 (mode=%s)", settings.sensor_mode)

    # ── 읽기 ──
    def snapshot(self) -> dict:
        with self._lock:
            temp, hum = self._temp, self._humidity
            online = time.time() - self._last_update < 10
            presence = time.time() - self._last_motion < settings.presence_timeout_sec
        data = {"temp": temp, "humidity": hum, "online": online, "presence": presence, "mode": settings.sensor_mode}
        # DHT11 은 오차가 크므로(온도 ±2°C, 습도 ±5%) 화면에는 반올림해서 보여주는 걸 권장
        if temp is not None and hum is not None:
            di = discomfort_index(temp, hum)
            data.update(
                discomfort=round(di, 1),
                discomfort_label=discomfort_label(di),
                humidity_label=humidity_label(hum),
            )
        return data

    # ── 아두이노로 명령 보내기 ──
    def send(self, command: str) -> bool:
        ser = self._ser
        if ser is None or not ser.is_open:
            log.info("[mock] 아두이노 명령: %s", command)
            return False
        try:
            ser.write((command + "\n").encode())
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("명령 전송 실패: %s", e)
            return False

    # ── 내부: 실제 시리얼 ──
    def _run_serial(self) -> None:
        import serial  # pyserial

        while True:
            try:
                self._ser = serial.Serial(settings.serial_port, settings.serial_baud, timeout=2)
                time.sleep(2)  # 포트를 열면 아두이노가 리셋되므로 잠깐 대기
                log.info("아두이노 연결됨: %s", settings.serial_port)
                while True:
                    line = self._ser.readline().decode(errors="ignore").strip()
                    if line:
                        self._handle_line(line)
            except Exception as e:  # noqa: BLE001
                log.warning("시리얼 오류(%s) → 3초 후 재시도", e)
                self._ser = None
                time.sleep(3)

    def _handle_line(self, line: str) -> None:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return  # 부팅 메시지 등 JSON 아닌 줄은 무시
        now = time.time()
        with self._lock:
            t, h = data.get("t"), data.get("h")
            if isinstance(t, (int, float)) and not math.isnan(t):
                self._temp = round(float(t), 1)
            if isinstance(h, (int, float)) and not math.isnan(h):
                self._humidity = round(float(h), 1)
            d = data.get("d")
            if isinstance(d, (int, float)) and 0 < d <= settings.presence_distance_cm:
                self._last_motion = now   # 초음파: 가까이 사람이 있음
            if data.get("pir") == 1:      # (PIR 센서를 쓰는 경우 하위 호환)
                self._last_motion = now
            self._last_update = now

    # ── 내부: 가짜 데이터 ──
    def _run_mock(self) -> None:
        temp, hum = 23.0, 45.0
        while True:
            temp = min(27, max(19, temp + random.uniform(-0.2, 0.2)))
            hum = min(65, max(30, hum + random.uniform(-0.5, 0.5)))
            with self._lock:
                self._temp, self._humidity = round(temp, 1), round(hum, 1)
                self._last_update = self._last_motion = time.time()
            time.sleep(2)


sensor_hub = SensorHub()
