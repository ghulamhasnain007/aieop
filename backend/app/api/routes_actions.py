from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.actions.service import ActionService, ActionDenied
from app.api.deps import get_current_role

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ActionRequest(BaseModel):
    agent_name: str
    action_type: str
    provider: str
    payload: dict
    actor_label: str = "unknown-user"
    reason: str = ""


class ApprovalRequest(BaseModel):
    approver_label: str = "unknown-approver"


@router.post("/request")
def request_action(req: ActionRequest, db: Session = Depends(get_db), role=Depends(get_current_role)):
    service = ActionService(db)
    try:
        outcome = service.request_action(
            agent_name=req.agent_name,
            action_type=req.action_type,
            provider=req.provider,
            payload=req.payload,
            acting_role=role,
            actor_label=req.actor_label,
            reason=req.reason,
        )
    except ActionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {
        "action_id": outcome.action.id,
        "status": outcome.status,
        "risk_level": outcome.action.risk_level,
        "detail": outcome.detail,
    }


@router.get("/pending")
def list_pending(db: Session = Depends(get_db)):
    service = ActionService(db)
    return [
        {
            "id": a.id,
            "agent_name": a.agent_name,
            "action_type": a.action_type,
            "risk_level": a.risk_level,
            "payload": a.payload,
            "created_at": a.created_at,
        }
        for a in service.list_pending()
    ]


@router.post("/{action_id}/approve")
def approve_action(action_id: str, req: ApprovalRequest, db: Session = Depends(get_db)):
    service = ActionService(db)
    try:
        outcome = service.approve(action_id, approver_label=req.approver_label)
    except ActionDenied as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"action_id": outcome.action.id, "status": outcome.status, "detail": outcome.detail}


@router.post("/{action_id}/reject")
def reject_action(action_id: str, req: ApprovalRequest, db: Session = Depends(get_db)):
    service = ActionService(db)
    try:
        outcome = service.reject(action_id, approver_label=req.approver_label)
    except ActionDenied as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"action_id": outcome.action.id, "status": outcome.status, "detail": outcome.detail}


audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


@audit_router.get("")
def list_audit(limit: int = 100, db: Session = Depends(get_db)):
    service = ActionService(db)
    return [
        {
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "reason": e.reason,
            "evidence": e.evidence,
            "result": e.result,
            "timestamp": e.timestamp,
        }
        for e in service.list_audit_trail(limit=limit)
    ]
