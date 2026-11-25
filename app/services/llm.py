"""LLM 연동 (Anthropic Claude API).

- briefing(): 미러 하단에 뜨는 '오늘의 브리핑' (30분 캐시)
- chat():     폰 관리 페이지에서 하는 대화 (코디/일정 상담)
API 키가 없거나 호출이 실패하면 규칙 기반 문구로 대체 → 미러가 멈추지 않는다.

다른 LLM(OpenAI, Ollama 등)으로 바꾸려면 _call() 한 함수만 고치면 된다.
"""
import time

from ..config import settings
from ..utils import log

SYSTEM_PROMPT = """너는 '스마트미러'에 탑재된 한국어 개인 비서야.
- 사용자의 날씨, 실내 환경, 일정, 할 일, 옷장, 추천 코디 정보를 JSON으로 받는다.
- 미러 화면에 표시되므로 짧고 친근하게 말해. (브리핑은 3~4문장, 이모지는 최대 2개)
- JSON에 없는 정보는 지어내지 말고, 모르면 모른다고 말해.
- 코디를 말할 땐 반드시 옷장(wardrobe)에 있는 옷 이름만 언급해."""

BRIEFING_PROMPT = "지금 상황을 바탕으로 오늘 아침 브리핑을 해줘. 날씨 → 추천 코디 → 오늘 일정/할 일 → 챙길 것 순서로."

_BRIEFING_TTL = 30 * 60
_briefing_cache = {"ts": 0.0, "value": None}


class LLMService:
    def __init__(self) -> None:
        self._client = None

    @property
    def available(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _call(self, system: str, messages: list[dict], max_tokens: int = 400) -> str:
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=settings.anthropic_api_key)
        resp = self._client.messages.create(
            model=settings.llm_model, max_tokens=max_tokens, system=system, messages=messages
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    # ── 아침 브리핑 ──
    def briefing(self, view: dict, force: bool = False) -> dict:
        fresh = _briefing_cache["value"] and time.time() - _briefing_cache["ts"] < _BRIEFING_TTL
        if fresh and not force:
            return _briefing_cache["value"]

        result = {"text": rule_based_briefing(view), "source": "rule"}
        if self.available:
            try:
                text = self._call(_system_with(view), [{"role": "user", "content": BRIEFING_PROMPT}], 300)
                result = {"text": text, "source": "llm"}
            except Exception as e:  # noqa: BLE001
                log.warning("LLM 브리핑 실패, 규칙 기반 사용: %s", e)
        _briefing_cache.update(ts=time.time(), value=result)
        return result

    # ── 대화 ──
    def chat(self, message: str, history: list[dict], view: dict) -> str:
        if not self.available:
            return "LLM API 키가 설정되지 않았어요. .env 의 ANTHROPIC_API_KEY 를 채워주세요."
        msgs = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-10:]
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
        ]
        while msgs and msgs[0]["role"] != "user":  # 첫 메시지는 user 여야 함
            msgs.pop(0)
        msgs.append({"role": "user", "content": message})
        try:
            return self._call(_system_with(view), msgs, 500)
        except Exception as e:  # noqa: BLE001
            log.warning("LLM 대화 실패: %s", e)
            return "지금은 AI 응답을 가져오지 못했어요. 잠시 후 다시 시도해 주세요."


def _system_with(view: dict) -> str:
    import json

    return SYSTEM_PROMPT + "\n\n[현재 상황 JSON]\n" + json.dumps(view, ensure_ascii=False)


def rule_based_briefing(view: dict) -> str:
    """LLM 없이 만드는 기본 브리핑."""
    parts = []
    w = view.get("weather")
    if w:
        parts.append(f"오늘은 {w['summary']}, 최저 {w['temp_min']:.0f}° / 최고 {w['temp_max']:.0f}°예요.")
    outfits = view.get("recommended_outfits") or []
    if outfits:
        best = outfits[0]
        names = ", ".join(v for v in (best["top"], best["bottom"], best["outer"]) if v)
        parts.append(f"추천 코디는 {names}.")
    events = view.get("events") or []
    if events:
        parts.append(f"첫 일정은 {events[0]['start']} {events[0]['title']}.")
    parts.extend(view.get("alerts") or [])
    return " ".join(parts) or "좋은 하루 보내세요!"


llm_service = LLMService()
