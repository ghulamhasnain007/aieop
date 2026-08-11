from unittest.mock import patch

from app.knowledge.rag_service import RagService
from app.llm import client as llm_client
from app.llm.narrate import narrate_root_cause
from app.agents.incident_agent import IncidentAgent
from app.models.entities import Project, Service, Repository, Commit, Build, Deployment, Alert
from datetime import datetime, timedelta


def test_rag_falls_back_to_extractive_without_api_key(db_session, monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_api_key", None)
    service = RagService(db_session)
    service.ingest_document(title="Runbook", content="Restart the service to clear the connection pool.")

    result = service.query("how do I fix the connection pool")

    assert result.grounded is True
    assert "From 'Runbook'" in result.answer  # extractive format, not LLM prose


def test_rag_uses_llm_when_configured(db_session, monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "sk-test")
    service = RagService(db_session)
    service.ingest_document(title="Runbook", content="Restart the service to clear the connection pool.")

    with patch("app.knowledge.rag_service.generate", return_value="Restart the service, per the Runbook.") as mock_gen:
        result = service.query("how do I fix the connection pool")

    assert result.answer == "Restart the service, per the Runbook."
    mock_gen.assert_called_once()


def test_rag_falls_back_if_llm_call_fails(db_session, monkeypatch):
    from app.llm.client import LLMError
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "sk-test")
    service = RagService(db_session)
    service.ingest_document(title="Runbook", content="Restart the service to clear the connection pool.")

    with patch("app.knowledge.rag_service.generate", side_effect=LLMError("boom")):
        result = service.query("how do I fix the connection pool")

    assert "From 'Runbook'" in result.answer  # fell back cleanly


def _seed_incident_scenario(db):
    project = Project(name="P"); db.add(project); db.commit(); db.refresh(project)
    service = Service(project_id=project.id, name="svc"); db.add(service); db.commit(); db.refresh(service)
    repo = Repository(project_id=project.id, provider="github", external_id="o/r", name="r")
    db.add(repo); db.commit(); db.refresh(repo)
    commit = Commit(repository_id=repo.id, sha="abc", message="fix", committed_at=datetime.utcnow() - timedelta(hours=1))
    db.add(commit); db.commit(); db.refresh(commit)
    build = Build(repository_id=repo.id, provider="github_actions", external_id="1", status="passed",
                  triggered_by_commit_id=commit.id)
    db.add(build); db.commit(); db.refresh(build)
    deploy_time = datetime.utcnow() - timedelta(minutes=40)
    deployment = Deployment(service_id=service.id, build_id=build.id, environment="production", deployed_at=deploy_time)
    db.add(deployment); db.commit(); db.refresh(deployment)
    alert = Alert(service_id=service.id, severity="critical", message="errors",
                  triggered_at=deploy_time + timedelta(minutes=3))
    db.add(alert); db.commit()
    return service


def test_narration_returns_none_without_api_key(db_session, monkeypatch):
    monkeypatch.setattr("app.llm.narrate.is_configured", lambda: False)
    service = _seed_incident_scenario(db_session)
    agent = IncidentAgent(db_session)
    result = agent.investigate(service.id, "test incident")

    assert narrate_root_cause(result) is None


def test_narration_uses_llm_when_configured(db_session, monkeypatch):
    monkeypatch.setattr("app.llm.narrate.is_configured", lambda: True)
    service = _seed_incident_scenario(db_session)
    agent = IncidentAgent(db_session)
    result = agent.investigate(service.id, "test incident")

    with patch("app.llm.narrate.generate", return_value="Deployment X caused the errors. Recommend rollback.") as mock_gen:
        narration = narrate_root_cause(result)

    assert narration == "Deployment X caused the errors. Recommend rollback."
    mock_gen.assert_called_once()


def test_narration_returns_none_for_insufficient_evidence(db_session, monkeypatch):
    monkeypatch.setattr("app.llm.narrate.is_configured", lambda: True)
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="svc")
    db_session.add(service); db_session.commit(); db_session.refresh(service)

    agent = IncidentAgent(db_session)
    result = agent.investigate(service.id, "no data")

    assert narrate_root_cause(result) is None
