from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.entities import Incident

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("")
def list_incidents(project_id: str, db: Session = Depends(get_db)):
    incidents = (
        db.query(Incident)
        .filter(Incident.project_id == project_id)
        .order_by(Incident.opened_at.desc())
        .all()
    )
    return [
        {
            "id": i.id,
            "title": i.title,
            "severity": i.severity,
            "status": i.status,
            "service_id": i.service_id,
            "root_cause_confidence": i.root_cause_confidence,
            "opened_at": i.opened_at,
            "resolved_at": i.resolved_at,
        }
        for i in incidents
    ]


@router.get("/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "id": incident.id,
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
        "service_id": incident.service_id,
        "root_cause_deployment_id": incident.root_cause_deployment_id,
        "root_cause_confidence": incident.root_cause_confidence,
        "evidence": incident.evidence,
        "opened_at": incident.opened_at,
        "resolved_at": incident.resolved_at,
    }
