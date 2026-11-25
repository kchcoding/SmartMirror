"""옷 등록/삭제 + 배경 제거(누끼).

누끼 방식: OpenCV GrabCut (설치 가벼움, 라즈베리파이에서도 동작).
  - 옷을 '단색 배경(바닥/침대 시트) 위에 펼쳐 놓고' 찍으면 결과가 좋다.
  - 투명 배경 PNG 를 올리면 누끼 과정을 건너뛴다.
OpenCV 가 없으면 원본을 그대로 쓴다. (시착 기능만 못 씀)
"""
import uuid

from ..database import WARDROBE_DIR, add_clothing, delete_clothing

CATEGORIES = {"top", "bottom", "outer"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 10 * 1024 * 1024


def save_upload(name: str, category: str, color: str, warmth: int, waterproof: bool, filename: str, content: bytes) -> int:
    if category not in CATEGORIES:
        raise ValueError("category 는 top / bottom / outer 중 하나여야 해요")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise ValueError("jpg, png, webp 이미지만 올릴 수 있어요")
    if len(content) > MAX_BYTES:
        raise ValueError("이미지는 10MB 이하여야 해요")

    uid = uuid.uuid4().hex
    original = f"{uid}{ext}"
    (WARDROBE_DIR / original).write_bytes(content)

    cutout = None
    try:
        cutout = f"{uid}_cutout.png"
        _make_cutout(WARDROBE_DIR / original, WARDROBE_DIR / cutout)
    except Exception as e:  # noqa: BLE001  (cv2 미설치, 이미지 깨짐 등)
        print(f"[wardrobe] 누끼 생성 실패, 원본 사용: {e}")
        cutout = None

    return add_clothing(name.strip(), category, color, max(1, min(5, warmth)), waterproof, original, cutout)


def remove(clothing_id: int) -> bool:
    item = delete_clothing(clothing_id)
    if not item:
        return False
    for fname in (item["image"], item["cutout"]):
        if fname:
            (WARDROBE_DIR / fname).unlink(missing_ok=True)
    return True


def _make_cutout(src, dst) -> None:
    import cv2
    import numpy as np

    img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("이미지를 읽을 수 없어요")

    # 이미 투명 배경이면 그대로 사용
    if img.ndim == 3 and img.shape[2] == 4:
        bgra = img
    else:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        scale = 600 / max(img.shape[:2])
        if scale < 1:  # 속도를 위해 최대 600px 로 축소
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        rect = (int(w * 0.03), int(h * 0.03), int(w * 0.94), int(h * 0.94))
        cv2.grabCut(img, mask, rect, np.zeros((1, 65)), np.zeros((1, 65)), 5, cv2.GC_INIT_WITH_RECT)
        fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        fg = cv2.GaussianBlur(fg, (5, 5), 0)  # 가장자리 부드럽게
        bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = fg

    # 투명 부분을 잘라내서 옷 영역에 딱 맞게 크롭
    ys, xs = np.where(bgra[:, :, 3] > 20)
    if len(xs) == 0:
        raise ValueError("옷 영역을 찾지 못했어요")
    bgra = bgra[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    cv2.imwrite(str(dst), bgra)
