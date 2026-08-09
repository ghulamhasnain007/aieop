"""
Timeline reconstruction (FR-036).

Walks the same chain the Incident Agent correlates over (commit -> build ->
deployment -> alert -> incident) and lays it out chronologically, exactly
in the shape shown in the requirements doc's example:

    09:10  Commit merged
    09:15  Build started
    ...

Reuses the incident's already-computed root_cause_deployment_id and
evidence (set by IncidentAgent.persist_root_cause) rather than
re-deriving correlation from scratch - the timeline should always tell
the same story as the root-cause analysis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import Incident, Deployment, Build, Commit, Alert


@dataclass
class TimelineEvent:
    timestamp: datetime
    label: str
    detail: str = ""


@dataclass
class IncidentTimeline:
    incident_id: str
    events: list[TimelineEvent] = field(default_factory=list)
    complete: bool = True   # False if some links in the chain couldn't be resolved
    notes: list[str] = field(default_factory=list)


class TimelineReconstructor:
    def __init__(self, db: Session):
        self.db = db

    def reconstruct(self, incident_id: str) -> IncidentTimeline:
        incident = self.db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            return IncidentTimeline(incident_id=incident_id, complete=False,
                                     notes=["No such incident"])

        events: list[TimelineEvent] = []
        notes: list[str] = []
        complete = True

        deployment = None
        if incident.root_cause_deployment_id:
            deployment = self.db.query(Deployment).filter(
                Deployment.id == incident.root_cause_deployment_id
            ).first()
        if not deployment:
            notes.append("No correlated deployment on this incident - timeline will be partial")
            complete = False

        if deployment:
            build = self.db.query(Build).filter(Build.id == deployment.build_id).first() \
                if deployment.build_id else None
            commit = None
            if build and build.triggered_by_commit_id:
                commit = self.db.query(Commit).filter(Commit.id == build.triggered_by_commit_id).first()

            if commit and commit.committed_at:
                events.append(TimelineEvent(
                    timestamp=commit.committed_at, label="Commit merged",
                    detail=commit.message or commit.sha or commit.id,
                ))
            elif build:
                notes.append("Build has no linked commit")

            if build:
                if build.started_at:
                    events.append(TimelineEvent(build.started_at, "Build started", build.id))
                if build.finished_at:
                    events.append(TimelineEvent(
                        build.finished_at,
                        "Build passed" if (build.status or "").lower() == "passed" else "Build finished",
                        build.id,
                    ))
            else:
                notes.append("Deployment has no linked build")

            if deployment.deployed_at:
                events.append(TimelineEvent(
                    deployment.deployed_at, "Deployment completed",
                    f"{deployment.environment or 'unknown environment'} ({deployment.id})",
                ))

        # Alerts: use every alert tied to this incident's service, not just
        # the one that triggered correlation, so the timeline shows the
        # full symptom picture.
        if incident.service_id:
            alerts = (
                self.db.query(Alert)
                .filter(Alert.service_id == incident.service_id)
                .order_by(Alert.triggered_at)
                .all()
            )
            for alert in alerts:
                if alert.triggered_at:
                    events.append(TimelineEvent(alert.triggered_at, "Alert triggered", alert.message or alert.id))

        if incident.opened_at:
            events.append(TimelineEvent(incident.opened_at, "Incident created", incident.title))
            if incident.root_cause_confidence is not None:
                events.append(TimelineEvent(
                    incident.opened_at, "AI investigation completed",
                    f"Confidence {incident.root_cause_confidence:.0%}",
                ))

        events.sort(key=lambda e: e.timestamp)

        return IncidentTimeline(incident_id=incident_id, events=events, complete=complete, notes=notes)
