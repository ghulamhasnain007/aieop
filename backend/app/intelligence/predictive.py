"""
Predictive sprint-risk model (FR-018).

This is deliberately a SEPARATE component from ProjectAgent.sprint_risk()
(the deterministic heuristic used for the chat answer) and from
health_score.py's sprint_health sub-score. The requirements doc calls out
predictive analytics as "an actual AI/ML evaluation component, rather than
using an LLM for everything" - so this exists to be a small, genuinely
explainable statistical model you can point to separately in an FYP
evaluation.

Model: logistic regression over four engineered features -
  x1 = fraction of sprint remaining (unstarted/in-progress work)
  x2 = velocity delta (this sprint's throughput vs the team's trailing
       average, negative = slowing down)
  x3 = overdue fraction
  x4 = high-priority unresolved fraction

    p(complete) = sigmoid(b0 + b1*x1 + b2*x2 + b3*x3 + b4*x4)

The coefficients below are EXPERT-ELICITED, not fitted from real
historical data (none exists yet for this project). This is explicitly
flagged rather than presented as a trained model. Once enough closed
sprints have accumulated in the `issues` table, replace `COEFFICIENTS`
with weights fit by an actual logistic regression (e.g.
sklearn.linear_model.LogisticRegression) over historical sprint outcomes
- the feature-engineering and prediction interface here don't need to
change, only the coefficient source.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import Issue

# (feature_name, coefficient) - expert-elicited, see module docstring
COEFFICIENTS = {
    "intercept": 1.2,
    "remaining_fraction": -2.1,
    "velocity_delta": 1.4,
    "overdue_fraction": -2.6,
    "high_priority_unresolved_fraction": -1.3,
}

DONE_STATUSES = {"done", "closed", "resolved"}
HIGH_PRIORITIES = {"high", "critical", "urgent"}


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


@dataclass
class SprintPrediction:
    sprint: str
    completion_probability: float
    features: dict[str, float]
    risk_factors: list[str] = field(default_factory=list)
    model_note: str = (
        "Coefficients are expert-elicited, not fit on historical data - "
        "see app.intelligence.predictive module docstring."
    )


class SprintRiskPredictor:
    def __init__(self, db: Session):
        self.db = db

    def predict(self, project_id: str, sprint: str, lookback_sprints: int = 3) -> SprintPrediction:
        current = (
            self.db.query(Issue)
            .filter(Issue.project_id == project_id, Issue.sprint == sprint)
            .all()
        )

        if not current:
            return SprintPrediction(
                sprint=sprint, completion_probability=0.5,
                features={}, risk_factors=["No issues found for this sprint - cannot compute features"],
            )

        total = len(current)
        done = sum(1 for i in current if (i.status or "").lower() in DONE_STATUSES)
        remaining_fraction = (total - done) / total

        overdue = sum(
            1 for i in current
            if i.due_date and i.due_date < datetime.utcnow()
            and (i.status or "").lower() not in DONE_STATUSES
        )
        overdue_fraction = overdue / total

        high_priority_unresolved = sum(
            1 for i in current
            if (i.priority or "").lower() in HIGH_PRIORITIES
            and (i.status or "").lower() not in DONE_STATUSES
        )
        high_priority_fraction = high_priority_unresolved / total

        velocity_delta = self._velocity_delta(project_id, sprint, done, lookback_sprints)

        features = {
            "remaining_fraction": round(remaining_fraction, 3),
            "velocity_delta": round(velocity_delta, 3),
            "overdue_fraction": round(overdue_fraction, 3),
            "high_priority_unresolved_fraction": round(high_priority_fraction, 3),
        }

        z = COEFFICIENTS["intercept"]
        for name, value in features.items():
            z += COEFFICIENTS[name] * value
        probability = round(_sigmoid(z), 3)

        risk_factors = []
        if remaining_fraction > 0.5:
            risk_factors.append(f"{int(remaining_fraction * 100)}% of sprint scope still remaining")
        if velocity_delta < -0.15:
            risk_factors.append(f"Velocity down {abs(velocity_delta):.0%} vs trailing average")
        if overdue_fraction > 0:
            risk_factors.append(f"{overdue} task(s) already overdue")
        if high_priority_fraction > 0.2:
            risk_factors.append("High proportion of unresolved high-priority work")

        return SprintPrediction(
            sprint=sprint, completion_probability=probability,
            features=features, risk_factors=risk_factors,
        )

    def _velocity_delta(self, project_id: str, current_sprint: str, current_done: int,
                         lookback_sprints: int) -> float:
        """Compares this sprint's completed-so-far count against the trailing
        average of *closed* sprints' final completed counts. Returns a
        fractional delta (-1..+inf), 0 if there's no history to compare to."""
        past_issues = (
            self.db.query(Issue)
            .filter(Issue.project_id == project_id, Issue.sprint != current_sprint)
            .all()
        )
        if not past_issues:
            return 0.0

        by_sprint: dict[str, list[Issue]] = {}
        for issue in past_issues:
            by_sprint.setdefault(issue.sprint or "unknown", []).append(issue)

        completed_counts = [
            sum(1 for i in issues if (i.status or "").lower() in DONE_STATUSES)
            for issues in by_sprint.values()
        ]
        completed_counts = completed_counts[-lookback_sprints:]
        if not completed_counts or sum(completed_counts) == 0:
            return 0.0

        avg_past = sum(completed_counts) / len(completed_counts)
        if avg_past == 0:
            return 0.0
        return (current_done - avg_past) / avg_past
