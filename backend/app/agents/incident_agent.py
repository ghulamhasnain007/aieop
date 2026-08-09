"""
Incident Agent (FR-012, FR-013, FR-014).

Correlation pipeline: Alert -> nearest prior Deployment -> Build -> Commit
-> (optionally) Issue. Confidence is a simple, explainable function of time
proximity, not a black-box score - this matters for FR-031 (explainable AI)
and FR-032 (must distinguish facts from hypotheses, never fabricate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import Alert, Deployment, Build, Commit, Incident


@dataclass
class Evidence:
    type: str      # "fact" | "hypothesis"
    source: str     # e.g. "alert", "deployment", "commit"
    id: str
    detail: str


@dataclass
class RootCauseResult:
    incident_title: str
    likely_cause: str | None
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    recommendation: str | None = None
    insufficient_evidence: bool = False


class IncidentAgent:
    name = "incident_agent"

    def __init__(self, db: Session):
        self.db = db

    def investigate(self, service_id: str, incident_title: str) -> RootCauseResult:
        latest_alert = (
            self.db.query(Alert)
            .filter(Alert.service_id == service_id)
            .order_by(Alert.triggered_at.desc())
            .first()
        )

        if not latest_alert:
            return RootCauseResult(
                incident_title=incident_title,
                likely_cause=None,
                confidence=0.0,
                insufficient_evidence=True,
                recommendation="I could not find enough evidence to determine the root cause. "
                               "No alerts are recorded for this service.",
            )

        evidence: list[Evidence] = [
            Evidence(type="fact", source="alert", id=latest_alert.id, detail=latest_alert.message or "Alert triggered"),
        ]

        # Find the nearest deployment to this service that happened BEFORE the alert.
        candidate_deployment = (
            self.db.query(Deployment)
            .filter(Deployment.service_id == service_id)
            .filter(Deployment.deployed_at != None)  # noqa: E711
            .filter(Deployment.deployed_at <= latest_alert.triggered_at)
            .order_by(Deployment.deployed_at.desc())
            .first()
        )

        if not candidate_deployment:
            return RootCauseResult(
                incident_title=incident_title,
                likely_cause=None,
                confidence=0.35,
                evidence=evidence,
                insufficient_evidence=True,
                recommendation="An alert was found but no prior deployment to correlate it with. "
                               "I cannot confidently identify a root cause - recommend manual investigation.",
            )

        evidence.append(Evidence(
            type="fact", source="deployment", id=candidate_deployment.id,
            detail=f"Deployed to {candidate_deployment.environment or 'unknown environment'} "
                   f"at {candidate_deployment.deployed_at}",
        ))

        # Time proximity drives confidence: the closer the deployment is to the
        # alert (within a plausible incident window), the stronger the signal.
        gap_minutes = (latest_alert.triggered_at - candidate_deployment.deployed_at).total_seconds() / 60
        if gap_minutes <= 10:
            confidence = 0.85
        elif gap_minutes <= 30:
            confidence = 0.65
        elif gap_minutes <= 120:
            confidence = 0.45
        else:
            confidence = 0.25

        commits: list[Commit] = []
        if candidate_deployment.build_id:
            build = self.db.query(Build).filter(Build.id == candidate_deployment.build_id).first()
            if build and build.triggered_by_commit_id:
                commit = self.db.query(Commit).filter(Commit.id == build.triggered_by_commit_id).first()
                if commit:
                    commits.append(commit)
                    evidence.append(Evidence(
                        type="fact", source="commit", id=commit.id,
                        detail=f"Commit {commit.sha[:8] if commit.sha else commit.id}: {commit.message}",
                    ))
                    confidence = min(confidence + 0.1, 0.95)

        evidence.append(Evidence(
            type="hypothesis", source="correlation", id=candidate_deployment.id,
            detail=f"Error alert followed this deployment by {int(gap_minutes)} minute(s) - "
                   f"time proximity suggests but does not prove causation",
        ))

        recommendation = None
        if confidence >= 0.6:
            recommendation = f"Recommend rollback of deployment {candidate_deployment.id}."
        else:
            recommendation = "Confidence is below the action threshold - recommend manual review before rollback."

        return RootCauseResult(
            incident_title=incident_title,
            likely_cause=f"Deployment {candidate_deployment.id}",
            confidence=round(confidence, 2),
            evidence=evidence,
            recommendation=recommendation,
            insufficient_evidence=False,
        )

    def persist_root_cause(self, incident: Incident, result: RootCauseResult) -> Incident:
        incident.root_cause_deployment_id = (
            result.likely_cause.split(" ")[-1] if result.likely_cause else None
        )
        incident.root_cause_confidence = result.confidence
        incident.evidence = [e.__dict__ for e in result.evidence]
        incident.status = "investigating" if not result.insufficient_evidence else "open"
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident
