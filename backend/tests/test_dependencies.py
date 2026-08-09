from app.models.entities import Project, Service
from app.intelligence.dependencies import DependencyAnalyzer


def test_direct_and_transitive_dependents_are_found(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)

    db_module = Service(project_id=project.id, name="database")
    db_session.add(db_module); db_session.commit(); db_session.refresh(db_module)

    payment = Service(project_id=project.id, name="payment-service", depends_on=[db_module.id])
    db_session.add(payment); db_session.commit(); db_session.refresh(payment)

    api = Service(project_id=project.id, name="api", depends_on=[payment.id])
    db_session.add(api); db_session.commit(); db_session.refresh(api)

    frontend = Service(project_id=project.id, name="frontend", depends_on=[api.id])
    db_session.add(frontend); db_session.commit(); db_session.refresh(frontend)

    db_session.commit()

    analyzer = DependencyAnalyzer(db_session)
    impact = analyzer.impact_of_failure(db_module.id)

    # If the database fails, payment -> api -> frontend are all transitively affected
    assert set(impact.dependents) == {"payment-service", "api", "frontend"}


def test_leaf_service_has_no_dependents(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    frontend = Service(project_id=project.id, name="frontend")
    db_session.add(frontend); db_session.commit(); db_session.refresh(frontend)

    analyzer = DependencyAnalyzer(db_session)
    impact = analyzer.impact_of_failure(frontend.id)

    assert impact.dependents == []


def test_unknown_service_flagged(db_session):
    analyzer = DependencyAnalyzer(db_session)
    impact = analyzer.impact_of_failure("nonexistent")
    assert impact.unknown_service is True
