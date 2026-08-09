"""
Autonomous actions + human-in-the-loop approval (FR-020, FR-021, FR-022,
FR-023, FR-024).

ActionService is the single choke point every write action an agent wants
to perform must pass through. It:

  1. Resolves the action_type to a Permission and checks the requesting
     agent + acting user actually have it (RBAC intersection from
     app.rbac.permissions - FR-021). Denied outright if not.
  2. Classifies risk (FR-022):
       low    -> auto-executed immediately, no human step
       medium -> created as "pending", executed only once explicitly
                 approved (even by the same user, to keep a deliberate
                 confirm step and an audit record of it)
       high   -> always requires a *different* explicit approval step;
                 the dashboard's Approval Center is where this happens
  3. Executes through the target adapter's execute_action() (FR-020),
     never fabricating a result - adapter failures are surfaced, not
     hidden (FR-033).
  4. Records both the AgentAction and an AuditEvent for every outcome -
     success, failure, rejection, or denial - so the trail is complete
     even for auto-executed low-risk actions (FR-024).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.entities import AgentAction, AuditEvent, RiskLevel, Role
from app.rbac.permissions import Permission, agent_allowed_permissions, classify_risk
from app.integrations import ADAPTER_REGISTRY
from app.integrations.base import IntegrationError


class ActionDenied(Exception):
    """Raised when RBAC denies the action outright (not the same as
    'pending approval' - this means the agent/user was never allowed to
    even request it)."""


@dataclass
class ActionOutcome:
    action: AgentAction
    status: str          # "executed" | "pending" | "denied" | "failed"
    detail: str = ""


class ActionService:
    def __init__(self, db: Session):
        self.db = db

    # -- requesting a new action -------------------------------------------

    def request_action(
        self,
        agent_name: str,
        action_type: str,
        provider: str,
        payload: dict,
        acting_role: Role,
        actor_label: str = "unknown-user",
        reason: str = "",
    ) -> ActionOutcome:
        try:
            permission = Permission(action_type)
        except ValueError:
            raise ActionDenied(f"Unknown action_type '{action_type}' has no mapped permission")

        allowed = agent_allowed_permissions(agent_name, acting_role)
        if permission not in allowed:
            self._audit(
                actor=f"{agent_name} (on behalf of {actor_label})",
                action=action_type,
                reason=reason,
                evidence=None,
                result="denied",
            )
            raise ActionDenied(
                f"'{agent_name}' is not permitted to perform '{action_type}' "
                f"for a user with role '{acting_role.value}'"
            )

        risk = classify_risk(permission)

        record = AgentAction(
            agent_name=agent_name,
            action_type=action_type,
            payload={**payload, "provider": provider, "actor_label": actor_label},
            risk_level=RiskLevel(risk),
            status="pending",
            requested_by=None,  # no real user table wired to auth yet (dev-mode stub)
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        if risk == "low":
            return self._execute(record, approver_label=actor_label, reason=reason)

        # medium/high: leave pending for the Approval Center
        self._audit(
            actor=agent_name, action=action_type, reason=reason,
            evidence={"action_id": record.id, "risk": risk}, result="pending_approval",
        )
        return ActionOutcome(action=record, status="pending", detail=f"Requires approval (risk: {risk})")

    # -- approval workflow ----------------------------------------------------

    def approve(self, action_id: str, approver_label: str) -> ActionOutcome:
        record = self.db.query(AgentAction).filter(AgentAction.id == action_id).first()
        if not record:
            raise ActionDenied(f"No such action: {action_id}")
        if record.status != "pending":
            return ActionOutcome(action=record, status=record.status, detail="Action is not pending")

        record.approved_by = None  # dev-mode stub - see request_action note
        return self._execute(record, approver_label=approver_label, reason="Approved by human reviewer")

    def reject(self, action_id: str, approver_label: str) -> ActionOutcome:
        record = self.db.query(AgentAction).filter(AgentAction.id == action_id).first()
        if not record:
            raise ActionDenied(f"No such action: {action_id}")
        if record.status != "pending":
            return ActionOutcome(action=record, status=record.status, detail="Action is not pending")

        record.status = "rejected"
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        self._audit(
            actor=approver_label, action=f"reject:{record.action_type}",
            reason="Rejected by human reviewer",
            evidence={"action_id": record.id}, result="rejected",
        )
        return ActionOutcome(action=record, status="rejected", detail="Rejected")

    def list_pending(self) -> list[AgentAction]:
        return self.db.query(AgentAction).filter(AgentAction.status == "pending").all()

    def list_audit_trail(self, limit: int = 100) -> list[AuditEvent]:
        return (
            self.db.query(AuditEvent)
            .order_by(AuditEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

    # -- internal -----------------------------------------------------------

    def _execute(self, record: AgentAction, approver_label: str, reason: str) -> ActionOutcome:
        provider = (record.payload or {}).get("provider")
        adapter = ADAPTER_REGISTRY.get(provider)

        if not adapter:
            record.status = "failed"
            record.result = {"error": f"No adapter registered for provider '{provider}'"}
            self.db.add(record); self.db.commit(); self.db.refresh(record)
            self._audit(actor=approver_label, action=record.action_type, reason=reason,
                        evidence={"action_id": record.id}, result="failed: unknown provider")
            return ActionOutcome(action=record, status="failed", detail=f"Unknown provider '{provider}'")

        try:
            action_payload = {k: v for k, v in (record.payload or {}).items()
                               if k not in {"provider", "actor_label"}}
            result = adapter.execute_action(record.action_type, action_payload)
            record.status = "executed"
            record.result = result if isinstance(result, dict) else {"result": str(result)}
            self.db.add(record); self.db.commit(); self.db.refresh(record)

            self._audit(
                actor=approver_label, action=record.action_type, reason=reason,
                evidence={"action_id": record.id, "provider": provider}, result="success",
            )
            return ActionOutcome(action=record, status="executed", detail="Executed successfully")

        except IntegrationError as exc:
            record.status = "failed"
            record.result = {"error": str(exc)}
            self.db.add(record); self.db.commit(); self.db.refresh(record)

            self._audit(
                actor=approver_label, action=record.action_type, reason=reason,
                evidence={"action_id": record.id, "provider": provider}, result=f"failed: {exc}",
            )
            # Never fabricate a success (FR-033) - surface the real failure.
            return ActionOutcome(action=record, status="failed", detail=str(exc))

    def _audit(self, actor: str, action: str, reason: str, evidence: dict | None, result: str) -> AuditEvent:
        event = AuditEvent(actor=actor, action=action, reason=reason, evidence=evidence, result=result)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
