from datetime import datetime, timedelta

from app.models.entities import Project, Service, Repository, Commit, Build, Deployment, Alert
from app.agents.incident_agent import IncidentAgent


def _seed_incident_scenario(db, gap_minutes=3):
    project = Project(name="Payments Platform")
    db.add(project); db.commit(); db.refresh(project)

    service = Service(project_id=project.id, name="payment-service", owner="ahmed")
    db.add(service); db.commit(); db.refresh(service)

    repo = Repository(project_id=project.id, provider="github", external_id="org/payments", name="payments")
    db.add(repo); db.commit(); db.refresh(repo)

    commit = Commit(
        repository_id=repo.id, sha="abc123def456", author="ahmed",
        message="Change token expiration handling", committed_at=datetime.utcnow() - timedelta(hours=1),
    )
    db.add(commit); db.commit(); db.refresh(commit)

    build = Build(
        repository_id=repo.id, provider="github_actions", external_id="run-382", status="passed",
        triggered_by_commit_id=commit.id,
    )
    db.add(build); db.commit(); db.refresh(build)

    deploy_time = datetime.utcnow() - timedelta(minutes=40)
    deployment = Deployment(
        service_id=service.id, build_id=build.id, environment="production",
        status="completed", deployed_at=deploy_time,
    )
    db.add(deployment); db.commit(); db.refresh(deployment)

    alert = Alert(
        service_id=service.id, source="simulated", severity="critical",
        message="Error rate exceeded threshold", triggered_at=deploy_time + timedelta(minutes=gap_minutes),
    )
    db.add(alert); db.commit(); db.refresh(alert)

    return service, deployment, commit


def test_incident_agent_finds_root_cause_with_high_confidence_for_close_deployment(db_session):
    service, deployment, commit = _seed_incident_scenario(db_session, gap_minutes=3)
    agent = IncidentAgent(db_session)

    result = agent.investigate(service.id, "Payment API failures")

    assert result.insufficient_evidence is False
    assert deployment.id in result.likely_cause
    assert result.confidence >= 0.85
    # commit evidence should be included since build->commit link exists
    assert any(e.source == "commit" and e.id == commit.id for e in result.evidence)
    # must explicitly separate fact from hypothesis (FR-032)
    assert any(e.type == "hypothesis" for e in result.evidence)
    assert all(e.type in {"fact", "hypothesis"} for e in result.evidence)


def test_incident_agent_lower_confidence_for_distant_deployment(db_session):
    service, deployment, commit = _seed_incident_scenario(db_session, gap_minutes=180)
    agent = IncidentAgent(db_session)

    result = agent.investigate(service.id, "Payment API failures")

    assert result.confidence <= 0.45


def test_incident_agent_never_fabricates_when_no_alerts(db_session):
    project = Project(name="Empty Project")
    db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="empty-service")
    db_session.add(service); db_session.commit(); db_session.refresh(service)

    agent = IncidentAgent(db_session)
    result = agent.investigate(service.id, "Mystery incident")

    assert result.insufficient_evidence is True
    assert result.likely_cause is None
    assert "could not find enough evidence" in result.recommendation.lower()
