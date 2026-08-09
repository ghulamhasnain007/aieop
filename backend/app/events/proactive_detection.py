"""
Event-driven proactive detection (FR-026, FR-027).

    Deployment -> Monitoring alert -> Incident Agent -> Correlation -> Incident created

This is the "system detects a problem before anyone asks" layer that
makes the platform more than a chatbot (demo Scenario 5 in the
requirements doc). It reuses IncidentAgent's correlation logic (same
evidence/confidence machinery, same fact-vs-hypothesis discipline) rather
than duplicating it - proactive detection and reactive investigation
should never disagree about *how* root cause is determined, only about
*what triggers* the investigation.

Production trigger note: the requirements doc's tech stack picks Redis
Streams for this (FR-026, NFR-003). This module exposes the pure
detection logic (`evaluate_service`) independently of any queue, so it
can be called either from an HTTP endpoint (as wired here for the FYP
demo) or from a Redis Streams consumer later without changing this code.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents.incident_agent import IncidentAgent, RootCauseResult
from app.models.entities import Alert, Deployment, Incident, Service


REGRESSION_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class ProactiveFinding:
    service_id: str
    triggered: bool
    reason: str
    root_cause: RootCauseResult | None = None
    created_incident_id: str | None = None
    alert_message: str | None = None


class ProactiveDetectionEngine:
    """Call `evaluate_service()` whenever a new alert or deployment event
    arrives for a service - see module docstring for the intended trigger."""

    def __init__(self, db: Session):
        self.db = db
        self.incident_agent = IncidentAgent(db)

    def evaluate_service(self, service_id: str) -> ProactiveFinding:
        service = self.db.query(Service).filter(Service.id == service_id).first()
        if not service:
            return ProactiveFinding(service_id=service_id, triggered=False, reason="Unknown service")

        latest_alert = (
            self.db.query(Alert)
            .filter(Alert.service_id == service_id)
            .order_by(Alert.triggered_at.desc())
            .first()
        )
        if not latest_alert:
            return ProactiveFinding(service_id=service_id, triggered=False, reason="No alerts recorded")

        # Has this exact alert already produced an incident? Don't duplicate.
        already_handled = (
            self.db.query(Incident)
            .filter(Incident.service_id == service_id)
            .filter(Incident.evidence.isnot(None))
            .all()
        )
        for incident in already_handled:
            for e in (incident.evidence or []):
                if e.get("source") == "alert" and e.get("id") == latest_alert.id:
                    return ProactiveFinding(
                        service_id=service_id, triggered=False,
                        reason=f"Alert {latest_alert.id} already has an associated incident",
                    )

        result = self.incident_agent.investigate(service_id, incident_title=f"Auto-detected: {service.name}")

        if result.insufficient_evidence or result.confidence < REGRESSION_CONFIDENCE_THRESHOLD:
            return ProactiveFinding(
                service_id=service_id, triggered=False,
                reason=f"Confidence {result.confidence:.0%} below the auto-trigger threshold "
                       f"({REGRESSION_CONFIDENCE_THRESHOLD:.0%}) - not raising a proactive incident",
                root_cause=result,
                alert_message=latest_alert.message,
            )

        # Confidence clears the bar: create the incident automatically and
        # attach the evidence, exactly as a human-triggered investigation would.
        incident = Incident(
            project_id=service.project_id,
            service_id=service_id,
            title=f"Auto-detected regression: {service.name}",
            severity=latest_alert.severity or "high",
            status="investigating",
        )
        self.incident_agent.persist_root_cause(incident, result)

        return ProactiveFinding(
            service_id=service_id, triggered=True,
            reason=f"Deployment correlated with alert at {result.confidence:.0%} confidence - "
                   f"incident auto-created",
            root_cause=result,
            created_incident_id=incident.id,
            alert_message=latest_alert.message,
        )

    def scan_all_services_with_recent_deployments(self) -> list[ProactiveFinding]:
        """Convenience batch entry point - in production this is what a
        Redis Streams consumer or a scheduled job would call. Evaluates
        every service that has at least one recorded deployment."""
        service_ids = [row[0] for row in self.db.query(Deployment.service_id).distinct().all()]
        return [self.evaluate_service(sid) for sid in service_ids]
