from datetime import datetime, timedelta

from app.models.entities import Project, Service, Repository, Commit, Build, Deployment, Incident
from app.intelligence.tech_debt import TechDebtDetector


def test_flags_service_with_repeated_incidents(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="payment-service")
    db_session.add(service); db_session.commit(); db_session.refresh(service)

    for i in range(4):
        db_session.add(Incident(project_id=project.id, service_id=service.id, title=f"Inc {i}",
                                opened_at=datetime.utcnow() - timedelta(days=i)))
    db_session.commit()

    detector = TechDebtDetector(db_session)
    signal = detector.analyze_service(service.id)

    assert signal.flagged is True
    assert signal.incident_count == 4
    assert "possible technical debt hotspot" in signal.message


def test_flags_service_with_high_commit_churn(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="svc")
    db_session.add(service); db_session.commit(); db_session.refresh(service)
    repo = Repository(project_id=project.id, provider="github", external_id="o/r", name="r")
    db_session.add(repo); db_session.commit(); db_session.refresh(repo)
    build = Build(repository_id=repo.id, provider="github_actions", external_id="1", status="passed")
    db_session.add(build); db_session.commit(); db_session.refresh(build)
    deployment = Deployment(service_id=service.id, build_id=build.id, environment="prod")
    db_session.add(deployment); db_session.commit()

    for i in range(12):
        db_session.add(Commit(repository_id=repo.id, sha=f"sha{i}",
                              committed_at=datetime.utcnow() - timedelta(days=i)))
    db_session.commit()

    detector = TechDebtDetector(db_session)
    signal = detector.analyze_service(service.id)

    assert signal.flagged is True
    assert signal.commit_count == 12


def test_healthy_service_is_not_flagged(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="healthy-service")
    db_session.add(service); db_session.commit(); db_session.refresh(service)

    detector = TechDebtDetector(db_session)
    signal = detector.analyze_service(service.id)

    assert signal.flagged is False
    assert signal.message is None
