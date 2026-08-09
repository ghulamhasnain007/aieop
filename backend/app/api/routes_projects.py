from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.entities import Project
from app.schemas.common import ProjectCreate
from app.intelligence.health_score import ProjectHealthScorer
from app.intelligence.risk_detection import RiskDetector

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@router.post("")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/health")
def project_health(project_id: str, db: Session = Depends(get_db)):
    """
    FR-017. Real weighted scoring over sprint/code/CI-CD/incident/security
    sub-scores, each computed from actual entity data - see
    app.intelligence.health_score for the formula and its documented
    placeholders (security_health has no real signal source yet).
    """
    scorer = ProjectHealthScorer(db)
    result = scorer.score(project_id)
    return {
        "project_id": result.project_id,
        "total": result.total,
        "breakdown": result.breakdown,
        "weights": result.weights,
        "risk_signals": [r.__dict__ for r in result.risk_signals],
        "notes": result.notes,
    }


@router.get("/{project_id}/risks")
def project_risks(project_id: str, db: Session = Depends(get_db)):
    """FR-016. Risk signals for the Risks dashboard panel."""
    detector = RiskDetector(db)
    return [r.__dict__ for r in detector.all_risks(project_id)]

