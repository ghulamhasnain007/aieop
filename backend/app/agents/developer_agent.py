"""
Developer Agent (FR-011). Queries the unified Commit/PullRequest tables to
answer "what changed" style questions and link code changes to issues.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.entities import Commit, PullRequest, Repository


@dataclass
class ChangeSummary:
    repository: str
    pull_requests: list[dict]
    commits: list[dict]
    potential_concerns: list[str]


class DeveloperAgent:
    name = "developer_agent"

    def __init__(self, db: Session):
        self.db = db

    def summarize_recent_changes(self, repository_id: str, limit: int = 20) -> ChangeSummary:
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        prs = (
            self.db.query(PullRequest)
            .filter(PullRequest.repository_id == repository_id)
            .order_by(PullRequest.merged_at.desc().nullslast())
            .limit(limit)
            .all()
        )
        commits = (
            self.db.query(Commit)
            .filter(Commit.repository_id == repository_id)
            .order_by(Commit.committed_at.desc())
            .limit(limit)
            .all()
        )

        concerns = []
        for pr in prs:
            if pr.deletions and pr.additions and pr.deletions > pr.additions * 2:
                concerns.append(f"PR '{pr.title}' removed far more code than it added - verify no functionality loss")
            if pr.additions and pr.additions > 800:
                concerns.append(f"PR '{pr.title}' is unusually large ({int(pr.additions)} additions) - higher review risk")

        return ChangeSummary(
            repository=repo.name if repo else repository_id,
            pull_requests=[{"id": p.id, "title": p.title, "author": p.author, "status": p.status} for p in prs],
            commits=[{"id": c.id, "sha": c.sha[:8] if c.sha else None, "message": c.message} for c in commits],
            potential_concerns=concerns,
        )

    def find_pull_requests_for_issue(self, issue_id: str) -> list[PullRequest]:
        return self.db.query(PullRequest).filter(PullRequest.issue_id == issue_id).all()
