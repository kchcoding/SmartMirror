"""환경설정. .env 파일(또는 환경변수)에서 값을 읽어옵니다.

값을 바꾸고 싶으면 코드를 고치지 말고 .env 만 수정하세요.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # 위치
    latitude: float = 35.115446
    longitude: float = 128.967669
    city_name: str = "부산"
    timezone: str = "Asia/Seoul"

    # 우산 알림
    rain_prob_threshold: int = 50      # 강수확률 이 값(%) 이상이면 알림
    rain_lookahead_hours: int = 12     # 앞으로 몇 시간까지 볼지

    # 센서 (아두이노)
    sensor_mode: str = "mock"          # mock | serial
    serial_port: str = "/dev/ttyACM0"
    serial_baud: int = 9600
    presence_distance_cm: int = 120    # 초음파 거리가 이 값 이하면 '거울 앞에 사람 있음'
    presence_timeout_sec: int = 30     # 이 시간 동안 감지 없으면 '자리 비움' (화면 꺼짐)

    # 캘린더
    ics_url: str = ""

    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"

    # 시착
    tryon_enabled: bool = False
    camera_index: int = 0

    # 데이터 저장 위치 (옷 사진, DB)
    data_dir: Path = BASE_DIR / "data"


settings = Settings()
