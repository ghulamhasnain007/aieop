"""
Taiga adapter (FR-003, FR-004). Swap for a Jira adapter with the same
interface if the target org uses Jira instead - the rest of the platform
(Project Agent, dashboard) only depends on BaseIntegration, never on Taiga
specifics.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.integrations.base import BaseIntegration, HealthStatus, NormalizedEvent, IntegrationError


class TaigaAdapter(BaseIntegration):
    provider_name = "taiga"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        cfg = config or {}
        self.base_url = cfg.get("base_url") or settings.taiga_base_url
        self.username = cfg.get("username") or settings.taiga_username
        self.password = cfg.get("password") or settings.taiga_password
        self._token: str | None = None

    def authenticate(self) -> bool:
        if not (self.base_url and self.username and self.password):
            self._authenticated = False
            return False
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/auth",
                json={"type": "normal", "username": self.username, "password": self.password},
                timeout=10,
            )
            if resp.status_code == 200:
                self._token = resp.json().get("auth_token")
                self._authenticated = True
            else:
                self._authenticated = False
        except httpx.HTTPError:
            self._authenticated = False
        return self._authenticated

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def retrieve(self, resource: str, **filters) -> list[dict[str, Any]]:
        if not self._token and not self.authenticate():
            raise IntegrationError("Taiga authentication failed or not configured")
        try:
            if resource == "issues":
                resp = httpx.get(
                    f"{self.base_url}/api/v1/issues",
                    headers=self._headers(),
                    params={"project": filters.get("project_id")},
                    timeout=15,
                )
            elif resource == "user_stories":
                resp = httpx.get(
                    f"{self.base_url}/api/v1/userstories",
                    headers=self._headers(),
                    params={"project": filters.get("project_id")},
                    timeout=15,
                )
            else:
                raise IntegrationError(f"Unknown resource '{resource}' for TaigaAdapter")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise IntegrationError(f"Taiga API request failed: {exc}") from exc

    def normalize(self, raw_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for obj in raw_objects:
            normalized.append({
                "entity_type": "issue",
                "external_id": str(obj.get("id")),
                "title": obj.get("subject"),
                "status": obj.get("status_extra_info", {}).get("name"),
                "assignee": obj.get("assigned_to_extra_info", {}).get("full_name_display"),
                "priority": obj.get("priority_extra_info", {}).get("name"),
                "sprint": obj.get("milestone_extra_info", {}).get("name") if obj.get("milestone_extra_info") else None,
                "due_date": obj.get("due_date"),
            })
        return normalized

    def get_events(self, since: datetime | None = None) -> list[NormalizedEvent]:
        return []

    def execute_action(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._token and not self.authenticate():
            raise IntegrationError("Cannot execute Taiga action: not authenticated")

        if action_type == "create_issue":
            resp = httpx.post(
                f"{self.base_url}/api/v1/issues",
                headers=self._headers(),
                json={
                    "project": payload["project_id"],
                    "subject": payload["title"],
                    "description": payload.get("body", ""),
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

        if action_type == "assign_issue":
            resp = httpx.patch(
                f"{self.base_url}/api/v1/issues/{payload['issue_id']}",
                headers=self._headers(),
                json={"assigned_to": payload["assignee_id"]},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

        raise IntegrationError(f"Unsupported Taiga action: {action_type}")

    def health_check(self) -> HealthStatus:
        if not (self.base_url and self.username and self.password):
            return HealthStatus(connected=False, detail="Taiga credentials not configured")
        ok = self.authenticate()
        return HealthStatus(connected=ok, detail="Connected" if ok else "Authentication failed")


BaseIntegration.register(TaigaAdapter())
