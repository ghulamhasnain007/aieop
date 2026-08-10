from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.demo.seed import seed_demo_project

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    """Creates (or returns the existing) demo project - see app.demo.seed
    for exactly what it sets up. Safe to call repeatedly."""
    return seed_demo_project(db)
