from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Project
from app.schemas.common import ProjectCreate

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
    FR-017 placeholder. Real weighted scoring (sprint/code/CI-CD/incident/
    security) lands in Phase 5 once enough entity data exists to compute it
    meaningfully; for now this documents the intended, configurable formula.
    """
    return {
        "project_id": project_id,
        "formula": {
            "sprint_health": 0.25,
            "code_health": 0.20,
            "cicd_health": 0.20,
            "incident_health": 0.20,
            "security_health": 0.15,
        },
        "note": "Scoring not yet computed - implemented in Phase 5 (see project plan).",
    }
