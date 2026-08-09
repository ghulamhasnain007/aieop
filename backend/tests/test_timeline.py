from datetime import datetime, timedelta

from app.models.entities import (
    Project, Service, Repository, Commit, Build, Deployment, Alert, Incident,
)
from app.agents.incident_agent import IncidentAgent
from app.intelligence.timeline import TimelineReconstructor


def _seed_full_chain(db):
    project = Project(name="P"); db.add(project); db.commit(); db.refresh(project)
    service = Service(project_id=project.id, name="payment-service")
    db.add(service); db.commit(); db.refresh(service)
    repo = Repository(project_id=project.id, provider="github", external_id="o/r", name="r")
    db.add(repo); db.commit(); db.refresh(repo)

    t0 = datetime(2026, 8, 1, 9, 10)
    commit = Commit(repository_id=repo.id, sha="abc123", message="fix timeout", committed_at=t0)
    db.add(commit); db.commit(); db.refresh(commit)

    build = Build(repository_id=repo.id, provider="github_actions", external_id="1", status="passed",
                  triggered_by_commit_id=commit.id, started_at=t0 + timedelta(minutes=5),
                  finished_at=t0 + timedelta(minutes=8))
    db.add(build); db.commit(); db.refresh(build)

    deployment = Deployment(service_id=service.id, build_id=build.id, environment="production",
                             deployed_at=t0 + timedelta(minutes=11))
    db.add(deployment); db.commit(); db.refresh(deployment)

    alert = Alert(service_id=service.id, severity="critical", message="error spike",
                  triggered_at=t0 + timedelta(minutes=17))
    db.add(alert); db.commit(); db.refresh(alert)

    incident = Incident(project_id=project.id, service_id=service.id, title="Payment outage",
                        opened_at=t0 + timedelta(minutes=21))
    agent = IncidentAgent(db)
    result = agent.investigate(service.id, "Payment outage")
    agent.persist_root_cause(incident, result)

    return incident


def test_timeline_events_are_chronologically_ordered(db_session):
    incident = _seed_full_chain(db_session)
    reconstructor = TimelineReconstructor(db_session)

    timeline = reconstructor.reconstruct(incident.id)

    assert timeline.complete is True
    timestamps = [e.timestamp for e in timeline.events]
    assert timestamps == sorted(timestamps)


def test_timeline_includes_all_expected_stages(db_session):
    incident = _seed_full_chain(db_session)
    reconstructor = TimelineReconstructor(db_session)

    timeline = reconstructor.reconstruct(incident.id)
    labels = [e.label for e in timeline.events]

    assert "Commit merged" in labels
    assert any("Build" in l for l in labels)
    assert "Deployment completed" in labels
    assert "Alert triggered" in labels
    assert "Incident created" in labels
    assert "AI investigation completed" in labels


def test_unknown_incident_returns_incomplete(db_session):
    reconstructor = TimelineReconstructor(db_session)
    timeline = reconstructor.reconstruct("does-not-exist")
    assert timeline.complete is False
    assert timeline.events == []
