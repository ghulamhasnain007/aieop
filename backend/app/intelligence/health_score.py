"""
Project Health Score (FR-017).

    Project Health = 25% Sprint Health + 20% Code Health + 20% CI/CD Health
                    + 20% Incident Health + 15% Security Health

Per the requirements doc's own instruction: "The exact formula should be
configurable and documented rather than presented as an objective
universal metric." Weights are a constructor parameter with the doc's
values as defaults; every sub-score function is independently callable so
a different weighting (or a replaced sub-score function) doesn't require
touching the others.

Security Health is NOT yet computed from real signals - there's no
Security Agent in this FYP's scope (it's explicitly Future Work in the
requirements doc). It returns a constant placeholder score, clearly
labeled as such, rather than fabricating a number that looks measured.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.entities import Issue, Repository, Build, Incident
from app.intelligence.risk_detection import RiskDetector, RiskSignal

DEFAULT_WEIGHTS = {
    "sprint_health": 0.25,
    "code_health": 0.20,
    "cicd_health": 0.20,
    "incident_health": 0.20,
    "security_health": 0.15,
}

SECURITY_HEALTH_PLACEHOLDER = 80  # see module docstring - not yet a real signal


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class HealthScoreResult:
    project_id: str
    total: float
    breakdown: dict[str, float]
    weights: dict[str, float]
    risk_signals: list[RiskSignal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ProjectHealthScorer:
    def __init__(self, db: Session, weights: dict[str, float] | None = None):
        self.db = db
        self.weights = weights or DEFAULT_WEIGHTS
        self.risk_detector = RiskDetector(db)

    def score(self, project_id: str) -> HealthScoreResult:
        notes: list[str] = []

        sprint = self._sprint_health(project_id, notes)
        code = self._code_health(project_id, notes)
        cicd = self._cicd_health(project_id, notes)
        incident = self._incident_health(project_id, notes)
        security = SECURITY_HEALTH_PLACEHOLDER
        notes.append("security_health is a fixed placeholder - no Security Agent implemented yet")

        breakdown = {
            "sprint_health": round(sprint, 1),
            "code_health": round(code, 1),
            "cicd_health": round(cicd, 1),
            "incident_health": round(incident, 1),
            "security_health": round(security, 1),
        }

        total = sum(breakdown[k] * self.weights.get(k, 0) for k in breakdown)

        risk_signals = self.risk_detector.project_risks(project_id) + \
            self.risk_detector.incident_risks(project_id)

        return HealthScoreResult(
            project_id=project_id, total=round(total, 1), breakdown=breakdown,
            weights=self.weights, risk_signals=risk_signals, notes=notes,
        )

    # -- sub-scores --------------------------------------------------------

    def _sprint_health(self, project_id: str, notes: list[str]) -> float:
        issues = self.db.query(Issue).filter(Issue.project_id == project_id).all()
        if not issues:
            notes.append("sprint_health: no issues found - returning neutral default (70)")
            return 70.0

        from datetime import datetime
        completed = sum(1 for i in issues if (i.status or "").lower() in {"done", "closed", "resolved"})
        overdue = sum(
            1 for i in issues
            if i.due_date and i.due_date < datetime.utcnow()
            and (i.status or "").lower() not in {"done", "closed", "resolved"}
        )
        completed_ratio = completed / len(issues)
        overdue_ratio = overdue / len(issues)
        return _clamp(100 * completed_ratio - 40 * overdue_ratio)

    def _code_health(self, project_id: str, notes: list[str]) -> float:
        repos = self.db.query(Repository).filter(Repository.project_id == project_id).all()
        if not repos:
            notes.append("code_health: no repositories found - returning neutral default (70)")
            return 70.0

        score = 100.0
        for repo in repos:
            for risk in self.risk_detector.code_risks(repo.id):
                score -= 25 if risk.severity == "high" else 15
        return _clamp(score)

    def _cicd_health(self, project_id: str, notes: list[str]) -> float:
        repos = self.db.query(Repository).filter(Repository.project_id == project_id).all()
        repo_ids = [r.id for r in repos]
        if not repo_ids:
            notes.append("cicd_health: no repositories found - returning neutral default (70)")
            return 70.0

        builds = self.db.query(Build).filter(Build.repository_id.in_(repo_ids)).all()
        if not builds:
            notes.append("cicd_health: no build history found - returning neutral default (80)")
            return 80.0

        passed = sum(1 for b in builds if (b.status or "").lower() == "passed")
        return _clamp(100 * passed / len(builds))

    def _incident_health(self, project_id: str, notes: list[str]) -> float:
        incidents = self.db.query(Incident).filter(Incident.project_id == project_id).all()
        if not incidents:
            return 100.0  # genuinely no incidents recorded is a real positive signal

        open_incidents = [i for i in incidents if i.status != "resolved"]
        critical_open = sum(1 for i in open_incidents if i.severity == "critical")
        other_open = len(open_incidents) - critical_open

        score = 100 - 25 * critical_open - 10 * other_open
        return _clamp(score)
