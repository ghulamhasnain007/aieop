"""
Project Agent (FR-010).

Phase-1/4 implementation: deterministic analysis over the unified Issue
table (sprint velocity, overdue count, workload). This is intentionally
NOT an LLM call - it's the structured "tool" layer the Coordinator/LLM
reasoning step will call into later, per the project plan ("tool functions
first, then the reasoning prompt").
"""
from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.entities import Issue


@dataclass
class SprintRiskResult:
    sprint: str
    total_tasks: int
    completed_tasks: int
    remaining_tasks: int
    overdue_tasks: int
    completion_probability: float
    risk_factors: list[str]


class ProjectAgent:
    name = "project_agent"

    def __init__(self, db: Session):
        self.db = db

    def sprint_risk(self, project_id: str, sprint: str) -> SprintRiskResult:
        issues = (
            self.db.query(Issue)
            .filter(Issue.project_id == project_id, Issue.sprint == sprint)
            .all()
        )
        total = len(issues)
        completed = sum(1 for i in issues if (i.status or "").lower() in {"done", "closed", "resolved"})
        remaining = total - completed
        now = datetime.utcnow()
        overdue = sum(
            1 for i in issues
            if i.due_date and i.due_date < now and (i.status or "").lower() not in {"done", "closed", "resolved"}
        )

        risk_factors = []
        if total == 0:
            probability = 0.5
            risk_factors.append("No issues found for this sprint - cannot compute a grounded estimate")
        else:
            completion_ratio = completed / total
            overdue_penalty = min(overdue * 0.08, 0.4)
            probability = max(0.0, min(1.0, completion_ratio + (1 - completion_ratio) * 0.3 - overdue_penalty))
            if overdue:
                risk_factors.append(f"{overdue} task(s) overdue")
            if remaining > total * 0.5:
                risk_factors.append("More than half the sprint's tasks remain")

        return SprintRiskResult(
            sprint=sprint,
            total_tasks=total,
            completed_tasks=completed,
            remaining_tasks=remaining,
            overdue_tasks=overdue,
            completion_probability=round(probability, 2),
            risk_factors=risk_factors,
        )

    def workload_by_assignee(self, project_id: str) -> dict[str, int]:
        issues = (
            self.db.query(Issue)
            .filter(Issue.project_id == project_id)
            .filter(Issue.status.notin_(["done", "closed", "resolved"]))
            .all()
        )
        workload: dict[str, int] = {}
        for issue in issues:
            key = issue.assignee or "unassigned"
            workload[key] = workload.get(key, 0) + 1
        return workload
