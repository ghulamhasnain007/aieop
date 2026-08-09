"""
Discord adapter (FR-003, FR-004). Handles inbound chat interaction and
outbound notifications (FR-027/028). Uses Discord's REST API directly
(no discord.py gateway connection needed for slash-command style usage).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.integrations.base import BaseIntegration, HealthStatus, NormalizedEvent, IntegrationError


class DiscordAdapter(BaseIntegration):
    provider_name = "discord"
    API_BASE = "https://discord.com/api/v10"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.token = (config or {}).get("token") or settings.discord_bot_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bot {self.token}"} if self.token else {}

    def authenticate(self) -> bool:
        if not self.token:
            self._authenticated = False
            return False
        try:
            resp = httpx.get(f"{self.API_BASE}/users/@me", headers=self._headers(), timeout=10)
            self._authenticated = resp.status_code == 200
        except httpx.HTTPError:
            self._authenticated = False
        return self._authenticated

    def retrieve(self, resource: str, **filters) -> list[dict[str, Any]]:
        if resource == "channel_messages":
            channel_id = filters.get("channel_id")
            try:
                resp = httpx.get(
                    f"{self.API_BASE}/channels/{channel_id}/messages",
                    headers=self._headers(),
                    params={"limit": filters.get("limit", 20)},
                    timeout=15,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                raise IntegrationError(f"Discord API request failed: {exc}") from exc
        raise IntegrationError(f"Unknown resource '{resource}' for DiscordAdapter")

    def normalize(self, raw_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "entity_type": "conversation",
                "external_id": obj.get("id"),
                "author": (obj.get("author") or {}).get("username"),
                "content": obj.get("content"),
                "created_at": obj.get("timestamp"),
            }
            for obj in raw_objects
        ]

    def get_events(self, since: datetime | None = None) -> list[NormalizedEvent]:
        return []

    def execute_action(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise IntegrationError("Cannot execute Discord action: no bot token configured")

        if action_type == "send_notification":
            channel_id = payload["channel_id"]
            resp = httpx.post(
                f"{self.API_BASE}/channels/{channel_id}/messages",
                headers=self._headers(),
                json={"content": payload["message"]},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

        raise IntegrationError(f"Unsupported Discord action: {action_type}")

    def health_check(self) -> HealthStatus:
        if not self.token:
            return HealthStatus(connected=False, detail="No DISCORD_BOT_TOKEN configured")
        ok = self.authenticate()
        return HealthStatus(connected=ok, detail="Connected" if ok else "Authentication failed")


BaseIntegration.register(DiscordAdapter())
