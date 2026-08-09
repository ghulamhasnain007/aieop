"""
GitHub adapter (FR-003, FR-004).

Real implementation against the GitHub REST API (read operations + issue
creation). Degrades gracefully to health_check(connected=False) if no token
is configured, rather than fabricating data (FR-033).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config.config import settings
from app.integrations.base import BaseIntegration, HealthStatus, NormalizedEvent, IntegrationError


class GitHubAdapter(BaseIntegration):
    provider_name = "github"
    API_BASE = "https://api.github.com"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.token = (config or {}).get("token") or settings.github_token
        self._client: httpx.Client | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def authenticate(self) -> bool:
        if not self.token:
            self._authenticated = False
            return False
        try:
            resp = httpx.get(f"{self.API_BASE}/user", headers=self._headers(), timeout=10)
            self._authenticated = resp.status_code == 200
        except httpx.HTTPError:
            self._authenticated = False
        return self._authenticated

    def retrieve(self, resource: str, **filters) -> list[dict[str, Any]]:
        """
        resource: "pull_requests" | "commits" | "repository" | "workflow_runs"
        filters must include repo="owner/name"
        """
        repo = filters.get("repo")
        if not repo:
            raise IntegrationError("GitHubAdapter.retrieve requires repo='owner/name'")

        try:
            if resource == "pull_requests":
                resp = httpx.get(
                    f"{self.API_BASE}/repos/{repo}/pulls",
                    headers=self._headers(),
                    params={"state": filters.get("state", "all"), "per_page": filters.get("limit", 20)},
                    timeout=15,
                )
            elif resource == "commits":
                resp = httpx.get(
                    f"{self.API_BASE}/repos/{repo}/commits",
                    headers=self._headers(),
                    params={"per_page": filters.get("limit", 20)},
                    timeout=15,
                )
            elif resource == "repository":
                resp = httpx.get(f"{self.API_BASE}/repos/{repo}", headers=self._headers(), timeout=15)
                resp.raise_for_status()
                return [resp.json()]
            elif resource == "workflow_runs":
                resp = httpx.get(
                    f"{self.API_BASE}/repos/{repo}/actions/runs",
                    headers=self._headers(),
                    params={"per_page": filters.get("limit", 20)},
                    timeout=15,
                )
                resp.raise_for_status()
                return resp.json().get("workflow_runs", [])
            else:
                raise IntegrationError(f"Unknown resource '{resource}' for GitHubAdapter")

            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise IntegrationError(f"GitHub API request failed: {exc}") from exc

    def normalize(self, raw_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for obj in raw_objects:
            if "workflow_id" in obj:  # GitHub Actions workflow run -> Build (FR-005)
                normalized.append({
                    "entity_type": "build",
                    "external_id": str(obj["id"]),
                    "status": {"success": "passed", "failure": "failed", "cancelled": "failed"}
                               .get(obj.get("conclusion"), obj.get("status")),
                    "started_at": obj.get("run_started_at"),
                    "finished_at": obj.get("updated_at"),
                    "commit_sha": (obj.get("head_commit") or {}).get("id") or obj.get("head_sha"),
                })
            elif "commit" in obj and "sha" in obj:  # commit object
                normalized.append({
                    "entity_type": "commit",
                    "external_id": obj["sha"],
                    "author": (obj.get("commit", {}).get("author") or {}).get("name"),
                    "message": obj.get("commit", {}).get("message"),
                    "committed_at": (obj.get("commit", {}).get("author") or {}).get("date"),
                })
            elif "number" in obj and "pull_request" not in obj:  # PR object
                normalized.append({
                    "entity_type": "pull_request",
                    "external_id": str(obj["number"]),
                    "title": obj.get("title"),
                    "author": (obj.get("user") or {}).get("login"),
                    "status": "merged" if obj.get("merged_at") else obj.get("state"),
                    "opened_at": obj.get("created_at"),
                    "merged_at": obj.get("merged_at"),
                    "additions": obj.get("additions"),
                    "deletions": obj.get("deletions"),
                })
        return normalized

    def get_events(self, since: datetime | None = None) -> list[NormalizedEvent]:
        # In production this reads GitHub webhook deliveries or polls the
        # Events API. Left as an extension point for Phase 2 wiring.
        return []

    def execute_action(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise IntegrationError("Cannot execute GitHub action: no token configured")

        if action_type == "create_issue":
            repo = payload["repo"]
            resp = httpx.post(
                f"{self.API_BASE}/repos/{repo}/issues",
                headers=self._headers(),
                json={"title": payload["title"], "body": payload.get("body", "")},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

        if action_type == "create_branch":
            repo = payload["repo"]
            resp = httpx.post(
                f"{self.API_BASE}/repos/{repo}/git/refs",
                headers=self._headers(),
                json={"ref": f"refs/heads/{payload['branch_name']}", "sha": payload["base_sha"]},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

        if action_type == "trigger_ci":
            repo = payload["repo"]
            workflow_id = payload["workflow_id"]  # filename (e.g. "ci.yml") or numeric id
            resp = httpx.post(
                f"{self.API_BASE}/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
                headers=self._headers(),
                json={"ref": payload.get("ref", "main")},
                timeout=15,
            )
            resp.raise_for_status()
            # GitHub returns 204 with no body on success
            return {"status": "dispatched", "repo": repo, "workflow_id": workflow_id}

        raise IntegrationError(f"Unsupported GitHub action: {action_type}")

    def health_check(self) -> HealthStatus:
        if not self.token:
            return HealthStatus(connected=False, detail="No GITHUB_TOKEN configured")
        ok = self.authenticate()
        return HealthStatus(connected=ok, detail="Connected" if ok else "Authentication failed")


# self-register a default instance so it shows up in ADAPTER_REGISTRY
BaseIntegration.register(GitHubAdapter())
