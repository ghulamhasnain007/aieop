from app.demo.seed import seed_demo_project
from app.models.entities import Project, Service, Incident, Issue


def test_seed_creates_full_scenario(db_session):
    result = seed_demo_project(db_session)

    assert result["already_seeded"] is False
    project = db_session.query(Project).filter(Project.id == result["project_id"]).first()
    assert project is not None

    services = db_session.query(Service).filter(Service.project_id == project.id).all()
    assert len(services) == 4

    incidents = db_session.query(Incident).filter(Incident.project_id == project.id).all()
    assert len(incidents) == 1
    assert incidents[0].root_cause_confidence is not None

    issues = db_session.query(Issue).filter(Issue.project_id == project.id).all()
    assert len(issues) == 6


def test_seed_is_idempotent(db_session):
    first = seed_demo_project(db_session)
    second = seed_demo_project(db_session)

    assert second["already_seeded"] is True
    assert first["project_id"] == second["project_id"]

    # confirm no duplicate services were created
    services = db_session.query(Service).filter(Service.project_id == first["project_id"]).all()
    assert len(services) == 4
