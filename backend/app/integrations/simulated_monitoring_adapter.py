"""
Simulated monitoring adapter (FR-003 stretch item).

Per the project plan's Phase 2 decision: standing up real Prometheus/Grafana
is unnecessary infrastructure cost for an FYP. This adapter emits synthetic
but *internally consistent* metrics/alerts so the Incident Agent has
something real to correlate against during development and demos. It
implements the exact same BaseIntegration interface, so swapping in a real
Prometheus adapter later requires no changes to the Incident Agent.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from app.integrations.base import BaseIntegration, HealthStatus, NormalizedEvent


class SimulatedMonitoringAdapter(BaseIntegration):
    provider_name = "simulated_monitoring"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._alerts: list[dict[str, Any]] = []

    def authenticate(self) -> bool:
        self._authenticated = True
        return True

    def seed_incident_scenario(self, service_name: str, deployment_time: datetime) -> dict[str, Any]:
        """
        Generates a coherent synthetic incident: error rate climbs a few
        minutes after a deployment, then an alert fires. Used by the
        Incident Agent demo scenario and by tests.
        """
        error_spike_time = deployment_time + timedelta(minutes=3)
        alert_time = error_spike_time + timedelta(minutes=2)
        alert = {
            "id": f"alert-{random.randint(1000, 9999)}",
            "service": service_name,
            "severity": "critical",
            "message": f"Error rate for {service_name} exceeded 5% threshold",
            "triggered_at": alert_time.isoformat(),
            "metric": "error_rate",
            "value": round(random.uniform(0.06, 0.15), 3),
            "baseline": round(random.uniform(0.005, 0.02), 3),
        }
        self._alerts.append(alert)
        return {
            "deployment_time": deployment_time.isoformat(),
            "error_spike_time": error_spike_time.isoformat(),
            "alert": alert,
        }

    def retrieve(self, resource: str, **filters) -> list[dict[str, Any]]:
        if resource == "alerts":
            service = filters.get("service")
            return [a for a in self._alerts if not service or a["service"] == service]
        if resource == "metrics":
            # cheap synthetic time series for a dashboard sparkline
            now = datetime.utcnow()
            return [
                {"timestamp": (now - timedelta(minutes=i)).isoformat(),
                 "error_rate": round(random.uniform(0.005, 0.02), 4)}
                for i in range(30, 0, -1)
            ]
        return []

    def normalize(self, raw_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for obj in raw_objects:
            if "metric" in obj:
                normalized.append({
                    "entity_type": "alert",
                    "external_id": obj["id"],
                    "severity": obj.get("severity"),
                    "message": obj.get("message"),
                    "triggered_at": obj.get("triggered_at"),
                })
        return normalized

    def get_events(self, since: datetime | None = None) -> list[NormalizedEvent]:
        events = []
        for a in self._alerts:
            ts = datetime.fromisoformat(a["triggered_at"])
            if since is None or ts >= since:
                events.append(NormalizedEvent(
                    entity_type="alert", entity_id=a["id"], event_type="triggered",
                    payload=a, occurred_at=ts,
                ))
        return events

    def execute_action(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Simulated monitoring adapter is read-only")

    def health_check(self) -> HealthStatus:
        return HealthStatus(connected=True, detail="Simulated source - always available")


BaseIntegration.register(SimulatedMonitoringAdapter())
