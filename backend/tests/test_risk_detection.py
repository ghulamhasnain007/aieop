from datetime import datetime, timedelta

from app.models.entities import Project, Issue, Repository, PullRequest, Commit, Service, Deployment, Incident
from app.intelligence.risk_detection import RiskDetector


def test_project_risks_flags_overdue_tasks(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    for i in range(6):
        db_session.add(Issue(
            project_id=project.id, provider="taiga", external_id=str(i), title=f"T{i}",
            status="open", due_date=datetime.utcnow() - timedelta(days=1),
        ))
    db_session.commit()

    detector = RiskDetector(db_session)
    signals = detector.project_risks(project.id)

    overdue_signals = [s for s in signals if "overdue" in s.message]
    assert len(overdue_signals) == 1
    assert overdue_signals[0].severity == "high"  # >5 overdue


def test_code_risks_flags_large_pr_and_hot_files(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    repo = Repository(project_id=project.id, provider="github", external_id="o/r", name="r")
    db_session.add(repo); db_session.commit(); db_session.refresh(repo)

    db_session.add(PullRequest(repository_id=repo.id, external_id="1", title="Big PR", additions=1200))
    for i in range(5):
        db_session.add(Commit(repository_id=repo.id, sha=f"sha{i}", files_changed=["payment_service.py"]))
    db_session.commit()

    detector = RiskDetector(db_session)
    signals = detector.code_risks(repo.id)

    assert any("large PR" in s.message for s in signals)
    assert any("payment_service.py" in s.message for s in signals)


def test_deployment_risks_flags_high_rollback_rate(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="svc"); db_session.add(service); db_session.commit(); db_session.refresh(service)

    for i in range(5):
        db_session.add(Deployment(service_id=service.id, environment="prod", rolled_back=(i < 3)))
    db_session.commit()

    detector = RiskDetector(db_session)
    signals = detector.deployment_risks(service.id)

    assert any("Rollback rate" in s.message for s in signals)
    assert any(s.severity == "high" for s in signals)  # 60% rollback rate


def test_incident_risks_flags_repeated_incidents_on_same_service(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    service = Service(project_id=project.id, name="svc"); db_session.add(service); db_session.commit(); db_session.refresh(service)

    for i in range(3):
        db_session.add(Incident(project_id=project.id, service_id=service.id, title=f"Incident {i}"))
    db_session.commit()

    detector = RiskDetector(db_session)
    signals = detector.incident_risks(project.id)

    assert any("recurring failure pattern" in s.message for s in signals)


def test_no_data_produces_no_false_risk_signals(db_session):
    project = Project(name="Empty"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    detector = RiskDetector(db_session)
    assert detector.all_risks(project.id) == []
