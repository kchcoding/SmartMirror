"""코디 추천 엔진 (규칙 기반).

LLM 없이도 항상 결과가 나오도록 '결정적(deterministic)' 로직으로 만들었다.
LLM 은 이 결과를 받아 '말로 설명/보조'하는 역할 (services/llm.py).

두께(warmth) 기준:
    1 매우 얇음 (반팔, 린넨)      2 얇음 (긴팔 티, 면바지, 가디건)
    3 보통 (맨투맨, 니트, 청바지, 자켓)   4 두꺼움 (기모, 코트)   5 매우 두꺼움 (패딩)
"""
import datetime as dt
import itertools
import random

from ..config import settings
from ..database import list_clothes

NEUTRALS = {"검정", "흰색", "회색", "네이비", "베이지"}

# (체감온도 하한, 상의 목표 두께, 하의 목표 두께, 아우터 목표 두께 / 0이면 불필요)
TEMP_TABLE = [
    (28, 1, 1, 0),
    (23, 1, 2, 0),
    (20, 2, 2, 0),
    (17, 2, 2, 2),
    (12, 3, 3, 3),
    (9, 3, 3, 4),
    (5, 4, 4, 4),
    (-100, 5, 4, 5),
]


def target_warmth(feels_like: float) -> dict:
    for min_temp, top, bottom, outer in TEMP_TABLE:
        if feels_like >= min_temp:
            return {"top": top, "bottom": bottom, "outer": outer}
    raise ValueError("unreachable")


def color_score(a: dict, b: dict) -> float:
    """무채색끼리는 안전, 무채색+포인트도 OK, 서로 다른 포인트 컬러 둘은 감점."""
    na, nb = a["color"] in NEUTRALS, b["color"] in NEUTRALS
    if na and nb:
        return 1.5
    if na or nb:
        return 1.0
    return 0.5 if a["color"] == b["color"] else -1.0


def _score(top, bottom, outer, target, rainy) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    score -= abs(top["warmth"] - target["top"]) * 2
    score -= abs(bottom["warmth"] - target["bottom"]) * 2

    if target["outer"] == 0:
        if outer:
            score -= 3  # 더운 날 아우터는 감점
    elif outer:
        score -= abs(outer["warmth"] - target["outer"]) * 2
        reasons.append("쌀쌀해서 겉옷이 필요해요")
    else:
        score -= 6      # 추운데 아우터가 없으면 크게 감점

    if rainy and outer:
        if outer["waterproof"]:
            score += 2
            reasons.append("비 예보라 방수 아우터로 골랐어요")
        else:
            score -= 1

    score += color_score(top, bottom)
    if outer:
        score += color_score(top, outer) * 0.5
    if top["warmth"] == target["top"]:
        reasons.append("상의 두께가 오늘 날씨에 딱 맞아요")
    return score, reasons


def recommend(weather: dict, today: dt.date | None = None, top_n: int = 3, clothes: list[dict] | None = None) -> dict:
    clothes = clothes if clothes is not None else list_clothes()
    tops = [c for c in clothes if c["category"] == "top"]
    bottoms = [c for c in clothes if c["category"] == "bottom"]
    outers = [c for c in clothes if c["category"] == "outer"]

    feels = weather["feels_like"]
    target = target_warmth(feels)
    base = {"feels_like": feels, "target": target, "candidates": [], "message": None}

    if not tops or not bottoms:
        base["message"] = "옷장에 상의와 하의를 먼저 등록해 주세요"
        return base

    rainy = weather.get("rain_prob_max", 0) >= settings.rain_prob_threshold or weather.get("precipitation", 0) > 0
    rng = random.Random((today or dt.date.today()).toordinal())  # 같은 날엔 같은 결과, 날마다 조금씩 다르게

    scored = []
    for top, bottom, outer in itertools.product(tops, bottoms, outers or [None]):
        s, reasons = _score(top, bottom, outer, target, rainy)
        scored.append((s + rng.uniform(0, 0.5), top, bottom, outer, reasons))
    scored.sort(key=lambda x: x[0], reverse=True)

    base["candidates"] = [
        {"top": t, "bottom": b, "outer": o, "score": round(s, 2), "reasons": r[:3] or ["무난한 조합이에요"]}
        for s, t, b, o, r in scored[:top_n]
    ]
    return base
