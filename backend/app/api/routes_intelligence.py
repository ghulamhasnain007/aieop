from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.intelligence.timeline import TimelineReconstructor
from app.intelligence.dependencies import DependencyAnalyzer
from app.intelligence.tech_debt import TechDebtDetector

router = APIRouter(tags=["intelligence"])


@router.get("/api/incidents/{incident_id}/timeline")
def incident_timeline(incident_id: str, db: Session = Depends(get_db)):
    reconstructor = TimelineReconstructor(db)
    result = reconstructor.reconstruct(incident_id)
    return {
        "incident_id": result.incident_id,
        "complete": result.complete,
        "notes": result.notes,
        "events": [
            {"timestamp": e.timestamp, "label": e.label, "detail": e.detail}
            for e in result.events
        ],
    }


@router.get("/api/services/{service_id}/dependencies")
def service_dependencies(service_id: str, db: Session = Depends(get_db)):
    analyzer = DependencyAnalyzer(db)
    result = analyzer.impact_of_failure(service_id)
    return {
        "service_id": result.service_id,
        "service_name": result.service_name,
        "unknown_service": result.unknown_service,
        "direct_dependencies": result.direct_dependencies,
        "potentially_affected_if_this_fails": result.dependents,
    }


@router.get("/api/services/{service_id}/tech-debt")
def service_tech_debt(service_id: str, window_days: int = 60, db: Session = Depends(get_db)):
    detector = TechDebtDetector(db)
    result = detector.analyze_service(service_id, window_days=window_days)
    return {
        "service_id": result.service_id,
        "service_name": result.service_name,
        "window_days": result.window_days,
        "incident_count": result.incident_count,
        "commit_count": result.commit_count,
        "flagged": result.flagged,
        "message": result.message,
    }
