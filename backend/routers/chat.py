from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import ChatRequest, ChatResponse
from services.ai_service import generate_reply

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)):
    history = [{"role": m.role, "content": m.content} for m in body.history]
    reply = generate_reply(db, body.message, history)
    return ChatResponse(reply=reply)
