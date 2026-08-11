"""
BaseIntegration (FR-004).

Every external system (GitHub, GitHub Actions, ...) implements this same
monitoring, docs) implements this same interface: authenticate, retrieve,
normalize, get_events, execute_action, health_check. Adapters self-register
into ADAPTER_REGISTRY on import so the Coordinator/dashboard can enumerate
"what's connected" without hardcoding a list (FR-034).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


ADAPTER_REGISTRY: dict[str, "BaseIntegration"] = {}


@dataclass
class HealthStatus:
    connected: bool
    detail: str = ""
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NormalizedEvent:
    """A platform event translated into the unified vocabulary (FR-005)."""
    entity_type: str      # "pull_request", "issue", "build", "alert", ...
    entity_id: str
    event_type: str       # "created", "updated", "merged", "failed", ...
    payload: dict[str, Any]
    occurred_at: datetime


class IntegrationError(Exception):
    """Raised by adapters on unrecoverable failure. Callers must NOT fabricate
    data when this is raised - surface a graceful error instead (FR-033)."""


class BaseIntegration(abc.ABC):
    """Abstract adapter. Subclasses register themselves via `register()`."""

    provider_name: str = "base"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._authenticated = False

    @classmethod
    def register(cls, instance: "BaseIntegration") -> None:
        ADAPTER_REGISTRY[instance.provider_name] = instance

    # --- required capabilities every adapter must implement -----------------

    @abc.abstractmethod
    def authenticate(self) -> bool:
        """Verify credentials / establish a client. Returns True on success."""

    @abc.abstractmethod
    def retrieve(self, resource: str, **filters) -> list[dict[str, Any]]:
        """Fetch raw platform-native objects (e.g. GitHub PRs)."""

    @abc.abstractmethod
    def normalize(self, raw_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Translate raw objects into the unified entity schema (FR-005)."""

    @abc.abstractmethod
    def get_events(self, since: datetime | None = None) -> list[NormalizedEvent]:
        """Return recent events for the event-driven layer (FR-026)."""

    @abc.abstractmethod
    def execute_action(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Perform a write action (create issue, trigger CI, ...). Must only
        be called after RBAC + risk-approval checks upstream (FR-022/023)."""

    @abc.abstractmethod
    def health_check(self) -> HealthStatus:
        """Cheap connectivity check for the Integration Health panel (FR-034)."""
