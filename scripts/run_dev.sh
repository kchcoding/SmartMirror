#!/usr/bin/env bash
# 개발용 실행 (코드 저장 시 자동 재시작). 노트북에서는 .env 의 SENSOR_MODE=mock 으로 두세요.
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
