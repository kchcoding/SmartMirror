"""LLM 비서 API: 아침 브리핑 + 대화."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.context import build_context, llm_view
from ..services.llm import llm_service

router = APIRouter(prefix="/api", tags=["assistant"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[dict] = []


@router.get("/briefing")
def briefing(refresh: bool = False):
    return llm_service.briefing(llm_view(build_context()), force=refresh)


@router.post("/assistant/chat")
def chat(body: ChatIn):
    reply = llm_service.chat(body.message, body.history, llm_view(build_context()))
    return {"reply": reply}
