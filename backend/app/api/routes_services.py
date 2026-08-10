from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.entities import Service

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("")
def list_services(project_id: str, db: Session = Depends(get_db)):
    services = db.query(Service).filter(Service.project_id == project_id).all()
    return [
        {"id": s.id, "name": s.name, "owner": s.owner, "depends_on": s.depends_on or []}
        for s in services
    ]
