"""
Engineering risk detection (FR-016).

Four risk categories, each computed from entities already in the unified
data model - no separate ML model needed for these, they're structural
signals. Each detector returns a list of RiskSignal so the caller (health
score, dashboard, chat) can both display them and use them as evidence.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import Issue, PullRequest, Commit, Deployment, Incident, Build, Repository, Service


@dataclass
class RiskSignal:
    category: str    # "project" | "code" | "deployment" | "incident"
    severity: str    # "low" | "medium" | "high"
    message: str


class RiskDetector:
    def __init__(self, db: Session):
        self.db = db

    # -- project risks: overdue tasks, workload imbalance ----------------------

    def project_risks(self, project_id: str) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        issues = self.db.query(Issue).filter(Issue.project_id == project_id).all()
        open_issues = [i for i in issues if (i.status or "").lower() not in {"done", "closed", "resolved"}]

        overdue = [i for i in open_issues if i.due_date and i.due_date < datetime.utcnow()]
        if overdue:
            severity = "high" if len(overdue) > 5 else "medium"
            signals.append(RiskSignal("project", severity, f"{len(overdue)} overdue task(s)"))

        workload = Counter(i.assignee or "unassigned" for i in open_issues)
        if workload:
            busiest, count = workload.most_common(1)[0]
            avg = sum(workload.values()) / len(workload)
            if count > avg * 2 and count >= 4:
                signals.append(RiskSignal(
                    "project", "medium",
                    f"Workload imbalance: {busiest} has {count} open tasks (avg {avg:.1f})",
                ))
        return signals

    # -- code risks: large PRs, hot files ---------------------------------------

    def code_risks(self, repository_id: str) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        prs = self.db.query(PullRequest).filter(PullRequest.repository_id == repository_id).all()

        large_prs = [p for p in prs if (p.additions or 0) > 800]
        if large_prs:
            signals.append(RiskSignal(
                "code", "medium", f"{len(large_prs)} unusually large PR(s) (>800 additions)",
            ))

        commits = self.db.query(Commit).filter(Commit.repository_id == repository_id).all()
        file_touch_counts: Counter[str] = Counter()
        for c in commits:
            for f in (c.files_changed or []):
                file_touch_counts[f] += 1

        hot_files = [f for f, n in file_touch_counts.items() if n >= 5]
        if hot_files:
            top_file, top_count = file_touch_counts.most_common(1)[0]
            signals.append(RiskSignal(
                "code", "medium" if len(hot_files) < 3 else "high",
                f"{len(hot_files)} high-change-frequency file(s); hottest is "
                f"'{top_file}' ({top_count} commits)",
            ))
        return signals

    # -- deployment risks: failure/rollback rate ---------------------------------

    def deployment_risks(self, service_id: str) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        deployments = self.db.query(Deployment).filter(Deployment.service_id == service_id).all()
        if not deployments:
            return signals

        rollbacks = sum(1 for d in deployments if d.rolled_back)
        rollback_rate = rollbacks / len(deployments)
        if rollback_rate > 0.2:
            signals.append(RiskSignal(
                "deployment", "high" if rollback_rate > 0.4 else "medium",
                f"Rollback rate {rollback_rate:.0%} over last {len(deployments)} deployment(s)",
            ))

        builds = self.db.query(Build).filter(Build.repository_id.in_(
            [d.build_id for d in deployments if d.build_id]
        )).all() if any(d.build_id for d in deployments) else []
        failed_builds = [b for b in builds if (b.status or "").lower() == "failed"]
        if builds and len(failed_builds) / len(builds) > 0.25:
            signals.append(RiskSignal(
                "deployment", "medium",
                f"{len(failed_builds)}/{len(builds)} recent builds failed",
            ))
        return signals

    # -- incident risks: repeated incidents on the same service -------------------

    def incident_risks(self, project_id: str) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        incidents = self.db.query(Incident).filter(Incident.project_id == project_id).all()
        if not incidents:
            return signals

        per_service = Counter(i.service_id for i in incidents if i.service_id)
        for service_id, count in per_service.items():
            if count >= 3:
                signals.append(RiskSignal(
                    "incident", "high" if count >= 5 else "medium",
                    f"Service {service_id} has {count} recorded incidents - recurring failure pattern",
                ))
        return signals

    def all_risks(self, project_id: str) -> list[RiskSignal]:
        signals = self.project_risks(project_id) + self.incident_risks(project_id)

        repos = self.db.query(Repository).filter(Repository.project_id == project_id).all()
        for repo in repos:
            signals.extend(self.code_risks(repo.id))

        services = self.db.query(Service).filter(Service.project_id == project_id).all()
        for service in services:
            signals.extend(self.deployment_risks(service.id))

        return signals
