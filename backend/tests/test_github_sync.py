from unittest.mock import patch

import pytest

from app.integrations.github_sync import sync_repository, GitHubSyncError
from app.models.entities import Repository, Commit, PullRequest, Issue, Build, Document

RAW_COMMITS = [
    {"sha": "abc123", "commit": {"author": {"name": "ahmed", "date": "2026-08-01T10:00:00Z"},
                                  "message": "Fix timeout handling"}},
]
RAW_PRS = [
    {"number": 42, "title": "Add retry logic", "user": {"login": "sara"},
     "state": "open", "merged_at": None, "created_at": "2026-08-01T09:00:00Z",
     "additions": 120, "deletions": 10, "head": {"ref": "feature/retry"}},
]
RAW_ISSUES = [
    {"number": 7, "title": "Investigate error spike", "state": "open",
     "assignee": {"login": "ahmed"}, "labels": [{"name": "priority: high"}],
     "milestone": {"title": "Sprint 14", "due_on": "2026-08-15T00:00:00Z"},
     "created_at": "2026-07-30T00:00:00Z"},
]
RAW_RUNS = [
    {"id": 999, "workflow_id": 1, "status": "completed", "conclusion": "success",
     "run_started_at": "2026-08-01T10:05:00Z", "updated_at": "2026-08-01T10:10:00Z",
     "head_sha": "abc123"},
]
RAW_README = [{"path": "README.md", "content": "# Demo Repo\n\nThis is a test repo."}]


def _mock_retrieve(resource, **filters):
    return {
        "commits": RAW_COMMITS, "pull_requests": RAW_PRS,
        "issues": RAW_ISSUES, "workflow_runs": RAW_RUNS, "readme": RAW_README,
    }[resource]


def test_sync_creates_all_expected_entities(db_session):
    with patch("app.integrations.github_sync.GitHubAdapter.authenticate", return_value=True), \
         patch("app.integrations.github_sync.GitHubAdapter.retrieve", side_effect=_mock_retrieve):
        result = sync_repository(db_session, project_id="proj-1", repo_full_name="acme/widgets")

    assert result["commits"] == 1
    assert result["pull_requests"] == 1
    assert result["issues"] == 1
    assert result["builds"] == 1
    assert result["documents"] == 1

    repo = db_session.query(Repository).filter(Repository.external_id == "acme/widgets").first()
    assert repo is not None

    commit = db_session.query(Commit).filter(Commit.repository_id == repo.id).first()
    assert commit.message == "Fix timeout handling"

    pr = db_session.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
    assert pr.title == "Add retry logic"

    issue = db_session.query(Issue).filter(Issue.project_id == "proj-1").first()
    assert issue.sprint == "Sprint 14"
    assert issue.priority == "high"

    build = db_session.query(Build).filter(Build.repository_id == repo.id).first()
    assert build.status == "passed"
    assert build.triggered_by_commit_id == commit.id  # linked via matching sha

    doc = db_session.query(Document).filter(Document.project_id == "proj-1").first()
    assert "Demo Repo" in doc.content


def test_sync_is_safe_to_rerun_without_duplicating(db_session):
    with patch("app.integrations.github_sync.GitHubAdapter.authenticate", return_value=True), \
         patch("app.integrations.github_sync.GitHubAdapter.retrieve", side_effect=_mock_retrieve):
        sync_repository(db_session, project_id="proj-1", repo_full_name="acme/widgets")
        second = sync_repository(db_session, project_id="proj-1", repo_full_name="acme/widgets")

    assert second["commits"] == 0
    assert second["pull_requests"] == 0
    assert second["issues"] == 0
    assert second["builds"] == 0

    repos = db_session.query(Repository).filter(Repository.external_id == "acme/widgets").all()
    assert len(repos) == 1


def test_sync_raises_clean_error_on_auth_failure(db_session):
    with patch("app.integrations.github_sync.GitHubAdapter.authenticate", return_value=False):
        with pytest.raises(GitHubSyncError):
            sync_repository(db_session, project_id="proj-1", repo_full_name="acme/widgets")
