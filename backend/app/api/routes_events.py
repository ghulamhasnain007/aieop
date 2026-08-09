from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.events.proactive_detection import ProactiveDetectionEngine

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("/evaluate-service/{service_id}")
def evaluate_service(service_id: str, db: Session = Depends(get_db)):
    """
    FR-026/027 demo trigger. In production this is called by a Redis
    Streams consumer reacting to a new deployment or alert event; for the
    FYP scope it's exposed as a directly-callable endpoint (e.g. from a
    'seed a new alert' demo script) so the proactive-detection scenario
    is runnable without standing up the queue.
    """
    engine = ProactiveDetectionEngine(db)
    finding = engine.evaluate_service(service_id)
    return {
        "service_id": finding.service_id,
        "triggered": finding.triggered,
        "reason": finding.reason,
        "created_incident_id": finding.created_incident_id,
        "confidence": finding.root_cause.confidence if finding.root_cause else None,
    }


@router.post("/scan-all")
def scan_all(db: Session = Depends(get_db)):
    engine = ProactiveDetectionEngine(db)
    findings = engine.scan_all_services_with_recent_deployments()
    return [
        {
            "service_id": f.service_id, "triggered": f.triggered, "reason": f.reason,
            "created_incident_id": f.created_incident_id,
        }
        for f in findings
    ]
