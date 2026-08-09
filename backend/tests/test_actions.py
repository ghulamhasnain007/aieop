import pytest

from app.actions.service import ActionService, ActionDenied
from app.models.entities import Role
from app.integrations.base import BaseIntegration, HealthStatus
from app.integrations import ADAPTER_REGISTRY


class FakeAdapter(BaseIntegration):
    """In-memory adapter for isolated tests - no real network calls."""
    provider_name = "fake"

    def __init__(self):
        super().__init__()
        self.calls = []
        self.should_fail = False

    def authenticate(self): return True
    def retrieve(self, resource, **filters): return []
    def normalize(self, raw_objects): return []
    def get_events(self, since=None): return []

    def execute_action(self, action_type, payload):
        from app.integrations.base import IntegrationError
        self.calls.append((action_type, payload))
        if self.should_fail:
            raise IntegrationError("simulated failure")
        return {"id": "ext-123", "action_type": action_type}

    def health_check(self):
        return HealthStatus(connected=True)


@pytest.fixture()
def fake_adapter():
    adapter = FakeAdapter()
    ADAPTER_REGISTRY["fake"] = adapter
    yield adapter
    del ADAPTER_REGISTRY["fake"]


def test_low_risk_action_auto_executes(db_session, fake_adapter):
    service = ActionService(db_session)
    outcome = service.request_action(
        agent_name="project_agent", action_type="read_project", provider="fake",
        payload={}, acting_role=Role.developer, actor_label="ahmed",
    )
    assert outcome.status == "executed"
    assert len(fake_adapter.calls) == 1


def test_medium_risk_action_requires_approval(db_session, fake_adapter):
    service = ActionService(db_session)
    outcome = service.request_action(
        agent_name="project_agent", action_type="create_issue", provider="fake",
        payload={"title": "bug"}, acting_role=Role.developer, actor_label="ahmed",
    )
    assert outcome.status == "pending"
    assert len(fake_adapter.calls) == 0  # not executed yet

    approved = service.approve(outcome.action.id, approver_label="tech_lead_sara")
    assert approved.status == "executed"
    assert len(fake_adapter.calls) == 1


def test_pending_action_can_be_rejected(db_session, fake_adapter):
    service = ActionService(db_session)
    outcome = service.request_action(
        agent_name="project_agent", action_type="create_issue", provider="fake",
        payload={"title": "bug"}, acting_role=Role.developer, actor_label="ahmed",
    )
    rejected = service.reject(outcome.action.id, approver_label="tech_lead_sara")
    assert rejected.status == "rejected"
    assert len(fake_adapter.calls) == 0


def test_rbac_denies_action_outside_agent_allow_list(db_session, fake_adapter):
    service = ActionService(db_session)
    # project_agent's tool allow-list does not include deploy_production
    with pytest.raises(ActionDenied):
        service.request_action(
            agent_name="project_agent", action_type="deploy_production", provider="fake",
            payload={}, acting_role=Role.system_admin, actor_label="admin",
        )


def test_action_failure_is_surfaced_not_fabricated(db_session, fake_adapter):
    fake_adapter.should_fail = True
    service = ActionService(db_session)
    outcome = service.request_action(
        agent_name="project_agent", action_type="read_project", provider="fake",
        payload={}, acting_role=Role.developer, actor_label="ahmed",
    )
    assert outcome.status == "failed"
    assert "simulated failure" in outcome.detail


def test_every_outcome_is_audited(db_session, fake_adapter):
    service = ActionService(db_session)
    service.request_action(
        agent_name="project_agent", action_type="read_project", provider="fake",
        payload={}, acting_role=Role.developer, actor_label="ahmed",
    )
    trail = service.list_audit_trail()
    assert len(trail) >= 1
    assert trail[0].result == "success"
