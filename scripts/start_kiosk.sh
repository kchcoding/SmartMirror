#!/usr/bin/env bash
# 라즈베리파이 부팅 시 미러 화면을 전체화면으로 띄운다.
# 서버(systemd)가 먼저 떠야 하므로 응답이 올 때까지 기다린 뒤 크로미움 실행.
until curl -sf http://localhost:8000/api/tryon/status > /dev/null; do sleep 2; done
chromium-browser --kiosk --noerrdialogs --disable-infobars --incognito --check-for-update-interval=31536000 http://localhost:8000/
