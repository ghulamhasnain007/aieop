from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.agents.coordinator import CoordinatorAgent
from app.memory.conversation_memory import ConversationMemory
from app.schemas.common import ChatRequest, ChatResponse
from app.api.deps import get_current_role
from app.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db), role=Depends(get_current_role)):
    memory = ConversationMemory(db, project_id=req.project_id, user_id=None, channel=req.channel)
    coordinator = CoordinatorAgent(db, low_confidence_threshold=settings.low_confidence_threshold)
    result = coordinator.handle(req.message, project_id=req.project_id, user_role=role, memory=memory)

    return ChatResponse(
        intent=result.intent.intent,
        domain=result.intent.domain,
        confidence=result.intent.confidence,
        risk_level=result.intent.risk_level,
        agent_used=result.agent_used,
        answer=result.answer,
        evidence=result.evidence,
        requires_clarification=result.requires_clarification,
    )
