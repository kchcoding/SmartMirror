"""날씨 + 대기질. Open-Meteo 사용 (API 키 필요 없음, 무료).

- 예보:   https://open-meteo.com/en/docs
- 대기질: https://open-meteo.com/en/docs/air-quality-api
"""
import httpx

from ..config import settings
from ..utils import ttl_cache

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# WMO weather code -> (한글 설명, 이모지)
WMO = {
    0: ("맑음", "☀️"), 1: ("대체로 맑음", "🌤️"), 2: ("구름 조금", "⛅"), 3: ("흐림", "☁️"),
    45: ("안개", "🌫️"), 48: ("안개", "🌫️"),
    51: ("약한 이슬비", "🌦️"), 53: ("이슬비", "🌦️"), 55: ("강한 이슬비", "🌦️"),
    56: ("언 이슬비", "🌧️"), 57: ("언 이슬비", "🌧️"),
    61: ("약한 비", "🌧️"), 63: ("비", "🌧️"), 65: ("강한 비", "🌧️"),
    66: ("언 비", "🌧️"), 67: ("언 비", "🌧️"),
    71: ("약한 눈", "🌨️"), 73: ("눈", "🌨️"), 75: ("강한 눈", "❄️"), 77: ("싸락눈", "🌨️"),
    80: ("약한 소나기", "🌦️"), 81: ("소나기", "🌧️"), 82: ("강한 소나기", "⛈️"),
    85: ("약한 눈보라", "🌨️"), 86: ("눈보라", "❄️"),
    95: ("뇌우", "⛈️"), 96: ("우박 동반 뇌우", "⛈️"), 99: ("우박 동반 뇌우", "⛈️"),
}


def describe(code: int) -> tuple[str, str]:
    return WMO.get(code, ("알 수 없음", "❔"))


@ttl_cache(600)  # 10분마다 갱신
def get_weather() -> dict:
    params = {
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "timezone": settings.timezone,
        "forecast_days": 2,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    }
    resp = httpx.get(FORECAST_URL, params=params, timeout=10)
    resp.raise_for_status()
    j = resp.json()
    cur, hourly, daily = j["current"], j["hourly"], j["daily"]

    # 현재 시각 이후 N시간치만 잘라서 사용
    times = hourly["time"]
    now_key = cur["time"][:13]  # 예: '2026-11-16T14'
    start = next((i for i, t in enumerate(times) if t[:13] >= now_key), 0)
    end = min(start + settings.rain_lookahead_hours, len(times))
    hours = [
        {
            "time": times[i],
            "hour": int(times[i][11:13]),
            "temp": hourly["temperature_2m"][i],
            "pop": hourly["precipitation_probability"][i] or 0,  # 강수확률 %
            "precip": hourly["precipitation"][i] or 0,           # 강수량 mm
            "code": hourly["weather_code"][i],
        }
        for i in range(start, end)
    ]

    summary, icon = describe(cur["weather_code"])
    return {
        "city": settings.city_name,
        "date": cur["time"][:10],
        "temp": cur["temperature_2m"],
        "feels_like": cur["apparent_temperature"],
        "humidity": cur["relative_humidity_2m"],
        "wind": cur["wind_speed_10m"],
        "precipitation": cur["precipitation"],
        "summary": summary,
        "icon": icon,
        "temp_max": daily["temperature_2m_max"][0],
        "temp_min": daily["temperature_2m_min"][0],
        "rain_prob_max": daily["precipitation_probability_max"][0] or 0,
        "hourly": hours,
    }


def _grade(value, limits) -> str:
    """한국 환경부 기준 4단계 (좋음/보통/나쁨/매우나쁨)."""
    if value is None:
        return "정보 없음"
    for label, limit in zip(("좋음", "보통", "나쁨"), limits):
        if value <= limit:
            return label
    return "매우나쁨"


@ttl_cache(1800)  # 30분마다 갱신
def get_air_quality() -> dict:
    params = {
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "timezone": settings.timezone,
        "current": "pm10,pm2_5",
    }
    resp = httpx.get(AIR_URL, params=params, timeout=10)
    resp.raise_for_status()
    cur = resp.json()["current"]
    pm25, pm10 = cur.get("pm2_5"), cur.get("pm10")
    return {
        "pm25": pm25,
        "pm10": pm10,
        "pm25_grade": _grade(pm25, (15, 35, 75)),
        "pm10_grade": _grade(pm10, (30, 80, 150)),
    }
