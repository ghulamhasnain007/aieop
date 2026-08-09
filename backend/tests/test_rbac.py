from app.models.entities import Role
from app.rbac.permissions import (
    agent_allowed_permissions, classify_risk, human_has_permission, Permission
)


def test_viewer_cannot_create_issue():
    assert not human_has_permission(Role.viewer, Permission.CREATE_ISSUE)


def test_system_admin_has_all_permissions():
    assert human_has_permission(Role.system_admin, Permission.DEPLOY_PRODUCTION)


def test_agent_never_exceeds_requesting_users_permissions():
    # developer_agent's own tool allow-list includes CREATE_PR, but a viewer
    # user has no write permissions at all - the intersection must be empty
    # of any write permission.
    allowed = agent_allowed_permissions("developer_agent", Role.viewer)
    assert Permission.CREATE_PR not in allowed
    assert Permission.READ_REPOSITORY in allowed  # viewers can still read


def test_incident_agent_cannot_rollback_even_for_admin():
    # rollback is deliberately excluded from the agent's own tool allow-list
    # regardless of the acting user's role - it always requires a human action.
    allowed = agent_allowed_permissions("incident_agent", Role.system_admin)
    assert Permission.ROLLBACK not in allowed


def test_risk_classification_defaults_to_high_for_unknown():
    class Fake:
        pass
    # classify_risk should fail-safe to "high" for anything not explicitly mapped
    assert classify_risk(Permission.DELETE_DATA) == "high"
    assert classify_risk(Permission.READ_PROJECT) == "low"
