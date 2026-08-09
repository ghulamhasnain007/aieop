from datetime import datetime, timedelta

from app.models.entities import Project, Service, Repository, Commit, Build, Deployment, Alert
from app.events.proactive_detection import ProactiveDetectionEngine


def _seed(db, gap_minutes=3):
    project = Project(name="P"); db.add(project); db.commit(); db.refresh(project)
    service = Service(project_id=project.id, name="payment-service"); db.add(service); db.commit(); db.refresh(service)
    repo = Repository(project_id=project.id, provider="github", external_id="o/r", name="r")
    db.add(repo); db.commit(); db.refresh(repo)
    commit = Commit(repository_id=repo.id, sha="abc123", message="change timeout handling",
                     committed_at=datetime.utcnow() - timedelta(hours=1))
    db.add(commit); db.commit(); db.refresh(commit)
    build = Build(repository_id=repo.id, provider="github_actions", external_id="1",
                  status="passed", triggered_by_commit_id=commit.id)
    db.add(build); db.commit(); db.refresh(build)
    deploy_time = datetime.utcnow() - timedelta(minutes=40)
    deployment = Deployment(service_id=service.id, build_id=build.id, environment="production",
                             deployed_at=deploy_time)
    db.add(deployment); db.commit(); db.refresh(deployment)
    alert = Alert(service_id=service.id, severity="critical", message="error rate spike",
                  triggered_at=deploy_time + timedelta(minutes=gap_minutes))
    db.add(alert); db.commit(); db.refresh(alert)
    return project, service, deployment, alert


def test_high_confidence_regression_auto_creates_incident(db_session):
    project, service, deployment, alert = _seed(db_session, gap_minutes=3)
    engine = ProactiveDetectionEngine(db_session)

    finding = engine.evaluate_service(service.id)

    assert finding.triggered is True
    assert finding.created_incident_id is not None
    assert finding.root_cause.confidence >= 0.6


def test_low_confidence_does_not_create_incident(db_session):
    project, service, deployment, alert = _seed(db_session, gap_minutes=180)
    engine = ProactiveDetectionEngine(db_session)

    finding = engine.evaluate_service(service.id)

    assert finding.triggered is False
    assert finding.created_incident_id is None
    assert "below the auto-trigger threshold" in finding.reason


def test_no_alerts_does_not_trigger(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="svc"); db_session.add(service); db_session.commit(); db_session.refresh(service)

    engine = ProactiveDetectionEngine(db_session)
    finding = engine.evaluate_service(service.id)

    assert finding.triggered is False
    assert finding.reason == "No alerts recorded"


def test_same_alert_does_not_create_duplicate_incidents(db_session):
    project, service, deployment, alert = _seed(db_session, gap_minutes=3)
    engine = ProactiveDetectionEngine(db_session)

    first = engine.evaluate_service(service.id)
    second = engine.evaluate_service(service.id)

    assert first.triggered is True
    assert second.triggered is False
    assert "already has an associated incident" in second.reason


def test_unknown_service_does_not_trigger(db_session):
    engine = ProactiveDetectionEngine(db_session)
    finding = engine.evaluate_service("nonexistent-id")
    assert finding.triggered is False
    assert finding.reason == "Unknown service"
