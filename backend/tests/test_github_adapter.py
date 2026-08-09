from app.integrations.github_adapter import GitHubAdapter


def test_normalize_workflow_run_maps_to_build_entity():
    adapter = GitHubAdapter()
    raw = [{
        "id": 382,
        "workflow_id": 111,
        "status": "completed",
        "conclusion": "failure",
        "run_started_at": "2026-08-01T10:00:00Z",
        "updated_at": "2026-08-01T10:05:00Z",
        "head_sha": "abc123def",
    }]

    normalized = adapter.normalize(raw)

    assert len(normalized) == 1
    assert normalized[0]["entity_type"] == "build"
    assert normalized[0]["status"] == "failed"
    assert normalized[0]["commit_sha"] == "abc123def"


def test_normalize_successful_run_maps_to_passed():
    adapter = GitHubAdapter()
    raw = [{"id": 1, "workflow_id": 1, "conclusion": "success", "head_sha": "x"}]
    normalized = adapter.normalize(raw)
    assert normalized[0]["status"] == "passed"


def test_health_check_reports_not_configured_without_token():
    adapter = GitHubAdapter(config={"token": None})
    status = adapter.health_check()
    assert status.connected is False
    assert "No GITHUB_TOKEN" in status.detail
