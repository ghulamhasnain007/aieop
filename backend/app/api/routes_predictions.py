from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.intelligence.predictive import SprintRiskPredictor

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/sprint-risk")
def predict_sprint_risk(project_id: str, sprint: str, db: Session = Depends(get_db)):
    predictor = SprintRiskPredictor(db)
    result = predictor.predict(project_id, sprint)
    return {
        "sprint": result.sprint,
        "completion_probability": result.completion_probability,
        "features": result.features,
        "risk_factors": result.risk_factors,
        "model_note": result.model_note,
    }
