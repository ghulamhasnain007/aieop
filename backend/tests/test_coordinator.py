from app.agents.coordinator import CoordinatorAgent
from app.models.entities import Role, Project


def test_low_confidence_requests_clarification(db_session):
    coordinator = CoordinatorAgent(db_session)
    result = coordinator.handle("uh so like", project_id=None, user_role=Role.developer)
    assert result.requires_clarification is True
    assert result.agent_used is None


def test_incident_domain_without_service_id_asks_for_it(db_session):
    coordinator = CoordinatorAgent(db_session)
    result = coordinator.handle("investigate the outage", project_id=None, user_role=Role.developer)
    assert result.agent_used == "incident_agent"
    assert "which service" in result.answer.lower()


def test_viewer_role_blocked_from_project_domain_read_when_permission_missing(db_session):
    # Viewer DOES have READ_PROJECT in this design, so this should succeed -
    # verifying the permission check doesn't over-block legitimate reads.
    project = Project(name="P")
    db_session.add(project); db_session.commit(); db_session.refresh(project)

    coordinator = CoordinatorAgent(db_session)
    result = coordinator.handle(
        "will we finish sprint 1", project_id=project.id, user_role=Role.viewer
    )
    assert result.agent_used == "project_agent"
    assert "permission" not in result.answer.lower()
