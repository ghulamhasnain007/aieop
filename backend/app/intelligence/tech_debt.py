"""
Technical debt detection (FR-039).

Reproduces the requirements doc's example almost exactly: "PaymentService
has generated 7 production incidents in the last 60 days and has been
modified in 14 emergency patches." We don't have a distinct "emergency
patch" flag on commits in the data model, so commit count in the window
is used as the churn proxy - documented explicitly below rather than
silently treated as equivalent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.entities import Incident, Deployment, Build, Commit, Service

INCIDENT_THRESHOLD = 3
COMMIT_CHURN_THRESHOLD = 10


@dataclass
class TechDebtSignal:
    service_id: str
    service_name: str
    window_days: int
    incident_count: int
    commit_count: int
    flagged: bool
    message: str | None = None


class TechDebtDetector:
    def __init__(self, db: Session):
        self.db = db

    def analyze_service(self, service_id: str, window_days: int = 60) -> TechDebtSignal:
        service = self.db.query(Service).filter(Service.id == service_id).first()
        service_name = service.name if service else service_id
        since = datetime.utcnow() - timedelta(days=window_days)

        incident_count = (
            self.db.query(Incident)
            .filter(Incident.service_id == service_id, Incident.opened_at >= since)
            .count()
        )

        deployments = self.db.query(Deployment).filter(Deployment.service_id == service_id).all()
        build_ids = [d.build_id for d in deployments if d.build_id]
        repo_ids = set()
        if build_ids:
            builds = self.db.query(Build).filter(Build.id.in_(build_ids)).all()
            repo_ids = {b.repository_id for b in builds}

        commit_count = 0
        if repo_ids:
            commit_count = (
                self.db.query(Commit)
                .filter(Commit.repository_id.in_(repo_ids), Commit.committed_at >= since)
                .count()
            )

        flagged = incident_count >= INCIDENT_THRESHOLD or commit_count >= COMMIT_CHURN_THRESHOLD
        message = None
        if flagged:
            message = (
                f"{service_name} has generated {incident_count} incident(s) and been touched by "
                f"{commit_count} commit(s) in the last {window_days} days - possible technical debt hotspot. "
                f"(Note: commit count is used as a churn proxy, not a count of 'emergency patches' - "
                f"the data model doesn't distinguish patch urgency.)"
            )

        return TechDebtSignal(
            service_id=service_id, service_name=service_name, window_days=window_days,
            incident_count=incident_count, commit_count=commit_count,
            flagged=flagged, message=message,
        )
