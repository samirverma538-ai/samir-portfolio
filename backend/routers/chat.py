from fastapi import APIRouter

from schemas import ChatRequest, ChatResponse
from services.ai_service import generate_reply

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in body.history]
    reply = generate_reply(body.message, history)
    return ChatResponse(reply=reply)
