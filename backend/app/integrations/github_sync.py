"""
GitHub repo sync (the real, non-demo data path).

Given a project and a GitHub `owner/repo`, pulls real commits, pull
requests, issues (with milestone -> sprint mapping), workflow runs
(-> Build), and the README (-> knowledge base) through GitHubAdapter and
persists them as unified entities. Every agent, risk detector, health
scorer, and RAG query then operates on real data instead of the demo
seed.

Upserts by (external_id) within the resolved Repository, so re-running a
sync is safe and just refreshes state - it never duplicates rows.
"""
from __future__ import annotations

from datetime import datetime

from dateutil import parser as dateparser
from sqlalchemy.orm import Session

from app.models.entities import Repository, Commit, PullRequest, Issue, Build
from app.integrations.github_adapter import GitHubAdapter
from app.integrations.base import IntegrationError
from app.knowledge.rag_service import RagService


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return dateparser.parse(value).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


class GitHubSyncError(Exception):
    pass


def sync_repository(db: Session, project_id: str, repo_full_name: str, token: str | None = None) -> dict:
    adapter = GitHubAdapter(config={"token": token} if token else None)
    if not adapter.authenticate():
        raise GitHubSyncError(
            "Could not authenticate with GitHub - check that a valid token is configured "
            "(GITHUB_TOKEN env var, or pass one explicitly)."
        )

    repository = db.query(Repository).filter(
        Repository.project_id == project_id, Repository.external_id == repo_full_name
    ).first()
    if not repository:
        repository = Repository(
            project_id=project_id, provider="github",
            external_id=repo_full_name, name=repo_full_name.split("/")[-1],
            url=f"https://github.com/{repo_full_name}",
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)

    counts = {"commits": 0, "pull_requests": 0, "issues": 0, "builds": 0, "documents": 0}

    try:
        # --- commits ---
        raw_commits = adapter.retrieve("commits", repo=repo_full_name, limit=50)
        for normalized in adapter.normalize(raw_commits):
            if normalized["entity_type"] != "commit":
                continue
            existing = db.query(Commit).filter(
                Commit.repository_id == repository.id, Commit.sha == normalized["external_id"]
            ).first()
            if existing:
                continue
            db.add(Commit(
                repository_id=repository.id, sha=normalized["external_id"],
                author=normalized.get("author"), message=normalized.get("message"),
                committed_at=_parse_dt(normalized.get("committed_at")),
            ))
            counts["commits"] += 1
        db.commit()

        # --- pull requests ---
        raw_prs = adapter.retrieve("pull_requests", repo=repo_full_name, limit=50)
        for normalized in adapter.normalize(raw_prs):
            if normalized["entity_type"] != "pull_request":
                continue
            existing = db.query(PullRequest).filter(
                PullRequest.repository_id == repository.id,
                PullRequest.external_id == normalized["external_id"],
            ).first()
            fields = dict(
                title=normalized.get("title"), author=normalized.get("author"),
                status=normalized.get("status"), additions=normalized.get("additions"),
                deletions=normalized.get("deletions"),
                opened_at=_parse_dt(normalized.get("opened_at")),
                merged_at=_parse_dt(normalized.get("merged_at")),
            )
            if existing:
                for key, value in fields.items():
                    setattr(existing, key, value)
            else:
                db.add(PullRequest(
                    repository_id=repository.id, external_id=normalized["external_id"], **fields
                ))
                counts["pull_requests"] += 1
        db.commit()

        # --- issues (milestone -> sprint) ---
        raw_issues = adapter.retrieve("issues", repo=repo_full_name, limit=50)
        for normalized in adapter.normalize(raw_issues):
            if normalized["entity_type"] != "issue":
                continue
            existing = db.query(Issue).filter(
                Issue.project_id == project_id, Issue.provider == "github",
                Issue.external_id == normalized["external_id"],
            ).first()
            fields = dict(
                title=normalized.get("title"), status=normalized.get("status"),
                assignee=normalized.get("assignee"), priority=normalized.get("priority"),
                sprint=normalized.get("sprint"), due_date=_parse_dt(normalized.get("due_date")),
            )
            if existing:
                for key, value in fields.items():
                    setattr(existing, key, value)
            else:
                db.add(Issue(
                    project_id=project_id, provider="github",
                    external_id=normalized["external_id"], **fields
                ))
                counts["issues"] += 1
        db.commit()

        # --- workflow runs -> builds ---
        raw_runs = adapter.retrieve("workflow_runs", repo=repo_full_name, limit=30)
        for normalized in adapter.normalize(raw_runs):
            if normalized["entity_type"] != "build":
                continue
            existing = db.query(Build).filter(
                Build.repository_id == repository.id, Build.external_id == normalized["external_id"]
            ).first()
            if existing:
                existing.status = normalized.get("status")
                continue
            commit = None
            if normalized.get("commit_sha"):
                commit = db.query(Commit).filter(
                    Commit.repository_id == repository.id, Commit.sha == normalized["commit_sha"]
                ).first()
            db.add(Build(
                repository_id=repository.id, provider="github_actions",
                external_id=normalized["external_id"], status=normalized.get("status"),
                triggered_by_commit_id=commit.id if commit else None,
                started_at=_parse_dt(normalized.get("started_at")),
                finished_at=_parse_dt(normalized.get("finished_at")),
            ))
            counts["builds"] += 1
        db.commit()

        # --- README -> knowledge base ---
        raw_readme = adapter.retrieve("readme", repo=repo_full_name)
        if raw_readme:
            rag = RagService(db)
            rag.ingest_document(
                title=f"{repo_full_name} README", project_id=project_id,
                source="github_sync", content=raw_readme[0]["content"],
            )
            counts["documents"] += 1

    except IntegrationError as exc:
        raise GitHubSyncError(str(exc)) from exc

    return {"repository_id": repository.id, "repo": repo_full_name, **counts}
