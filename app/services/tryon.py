"""가상 시착 (카메라 + MediaPipe Pose + 옷 PNG 합성).

원리:
  1) 카메라 프레임을 좌우 반전(거울처럼)
  2) MediaPipe Pose 로 어깨/골반/발목 좌표를 찾는다
  3) 그 좌표에 맞춰 옷 누끼 PNG 를 크기 조절해서 알파 블렌딩
  4) JPEG 로 인코딩해서 MJPEG 스트림(/api/tryon/stream)으로 송출

한계(발표 때 솔직하게 말하는 게 좋아요): 옷을 '늘려 붙이는' 2D 합성이라 팔 움직임/주름/
입체감은 표현하지 못한다. 진짜 가상 피팅(diffusion 기반)은 라즈베리파이에서 불가능.
"""
import threading
import time

from ..config import settings
from ..database import WARDROBE_DIR, get_clothing
from ..utils import log

# MediaPipe Pose 랜드마크 번호
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24
L_ANKLE, R_ANKLE = 27, 28


class TryOnEngine:
    def __init__(self) -> None:
        self.available = False
        self.error: str | None = None
        self.selection: dict[str, int] = {}
        self._jpeg: bytes | None = None
        self._last_request = 0.0
        self._garments: dict[str, object] = {}

    # ── 외부 인터페이스 ──
    def start(self) -> None:
        if not settings.tryon_enabled:
            self.error = "시착 기능이 꺼져 있어요 (.env 의 TRYON_ENABLED=true)"
            return
        threading.Thread(target=self._loop, daemon=True, name="tryon").start()

    def set_selection(self, selection: dict) -> None:
        self.selection = {k: v for k, v in selection.items() if v}

    def status(self) -> dict:
        return {"enabled": settings.tryon_enabled, "available": self.available,
                "error": self.error, "selection": self.selection}

    def mjpeg(self):
        """브라우저 <img> 태그가 읽을 수 있는 multipart 스트림 생성기."""
        while True:
            self._last_request = time.time()  # '누가 보고 있다' 표시 → 아무도 안 보면 처리 중단
            if self._jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + self._jpeg + b"\r\n"
            time.sleep(0.06)

    # ── 내부 루프 ──
    def _loop(self) -> None:
        try:
            import cv2
            import mediapipe as mp
        except ImportError as e:
            self.error = f"비전 라이브러리 미설치: pip install -r requirements-vision.txt ({e})"
            log.warning(self.error)
            return

        cap = cv2.VideoCapture(settings.camera_index)
        if not cap.isOpened():
            self.error = "카메라를 열 수 없어요 (CAMERA_INDEX 확인)"
            log.warning(self.error)
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # 라즈베리파이 성능을 위해 640x480
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        pose = mp.solutions.pose.Pose(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.available = True
        log.info("시착 엔진 준비 완료")

        while True:
            if time.time() - self._last_request > 5:  # 보는 사람이 없으면 쉰다 (CPU 절약)
                time.sleep(0.2)
                continue
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            frame = cv2.flip(frame, 1)
            result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if result.pose_landmarks:
                self._draw_outfit(frame, result.pose_landmarks.landmark)
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                self._jpeg = buf.tobytes()

    # ── 합성 ──
    def _garment(self, category: str):
        import cv2

        clothing_id = self.selection.get(category)
        if not clothing_id:
            return None
        item = get_clothing(clothing_id)
        if not item or not item["cutout"]:
            return None
        key = item["cutout"]
        if key not in self._garments:
            img = cv2.imread(str(WARDROBE_DIR / key), cv2.IMREAD_UNCHANGED)
            if img is not None and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            self._garments[key] = img
        return self._garments[key]

    def _draw_outfit(self, frame, lm) -> None:
        h, w = frame.shape[:2]

        def pt(i):
            p = lm[i]
            return p.x * w, p.y * h, p.visibility

        ls, rs, lh, rh = pt(L_SHOULDER), pt(R_SHOULDER), pt(L_HIP), pt(R_HIP)
        if min(ls[2], rs[2], lh[2], rh[2]) < 0.5:
            return  # 몸통이 잘 안 보이면 합성하지 않음

        sx, sy = (ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2   # 어깨 중앙
        hx, hy = (lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2   # 골반 중앙
        shoulder_w, hip_w, torso = abs(ls[0] - rs[0]), abs(lh[0] - rh[0]), hy - sy
        if torso <= 0 or shoulder_w <= 0:
            return

        # 그리는 순서: 하의 → 상의 → 아우터 (위에 덮이도록)
        bottom = self._garment("bottom")
        if bottom is not None:
            la, ra = pt(L_ANKLE), pt(R_ANKLE)
            ankle_y = max(la[1], ra[1]) if min(la[2], ra[2]) > 0.3 else min(h, hy + torso * 1.9)
            bw = max(hip_w * 1.8, shoulder_w * 1.2)
            y0 = hy - torso * 0.05
            _overlay(frame, bottom, hx - bw / 2, y0, bw, ankle_y - y0)

        top = self._garment("top")
        if top is not None:
            tw = shoulder_w * 1.9                      # 소매 폭까지 고려해서 어깨보다 넓게
            y0 = sy - torso * 0.15
            _overlay(frame, top, sx - tw / 2, y0, tw, (hy + torso * 0.12) - y0)

        outer = self._garment("outer")
        if outer is not None:
            ow = shoulder_w * 2.15
            y0 = sy - torso * 0.18
            _overlay(frame, outer, sx - ow / 2, y0, ow, (hy + torso * 0.35) - y0)


def _overlay(frame, garment, x, y, w, h) -> None:
    """frame 위에 투명 PNG(garment)를 (x, y, w, h) 영역으로 알파 블렌딩."""
    import cv2
    import numpy as np

    x, y, w, h = int(x), int(y), int(w), int(h)
    if w < 10 or h < 10:
        return
    g = cv2.resize(garment, (w, h), interpolation=cv2.INTER_AREA)

    # 화면 밖으로 나간 부분 잘라내기
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, frame.shape[1]), min(y + h, frame.shape[0])
    if x0 >= x1 or y0 >= y1:
        return
    g = g[y0 - y: y1 - y, x0 - x: x1 - x]

    alpha = g[:, :, 3:4].astype(np.float32) / 255.0
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (alpha * g[:, :, :3] + (1 - alpha) * roi).astype(np.uint8)


tryon_engine = TryOnEngine()
