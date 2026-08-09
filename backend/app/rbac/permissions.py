"""
RBAC (FR-021, FR-040).

Two layers:

1. Human roles -> what a person can see/do in the API/dashboard.
2. Agent permissions -> what tools each AI agent is allowed to call, on top
   of (never exceeding) the permissions of the user on whose behalf it acts.
   This is the critical safety property from the original Agent Bridge spec:
   an agent must never auto-inherit administrator privileges.
"""
from dataclasses import dataclass, field
from enum import Enum

from app.models.entities import Role


class Permission(str, Enum):
    READ_REPOSITORY = "read_repository"
    READ_PROJECT = "read_project"
    READ_INCIDENT = "read_incident"
    CREATE_ISSUE = "create_issue"
    UPDATE_ISSUE = "update_issue"
    ASSIGN_ISSUE = "assign_issue"
    CREATE_BRANCH = "create_branch"
    CREATE_PR = "create_pr"
    MERGE_PR = "merge_pr"
    TRIGGER_CI = "trigger_ci"
    DEPLOY_PRODUCTION = "deploy_production"
    ROLLBACK = "rollback"
    RESTART_SERVICE = "restart_service"
    SEND_NOTIFICATION = "send_notification"
    GENERATE_REPORT = "generate_report"
    DELETE_DATA = "delete_data"
    APPROVE_ACTION = "approve_action"


# --- Human role -> permission set -------------------------------------------------

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.system_admin: set(Permission),
    Role.engineering_manager: {
        Permission.READ_REPOSITORY, Permission.READ_PROJECT, Permission.READ_INCIDENT,
        Permission.CREATE_ISSUE, Permission.UPDATE_ISSUE, Permission.ASSIGN_ISSUE,
        Permission.GENERATE_REPORT, Permission.APPROVE_ACTION, Permission.SEND_NOTIFICATION,
    },
    Role.tech_lead: {
        Permission.READ_REPOSITORY, Permission.READ_PROJECT, Permission.READ_INCIDENT,
        Permission.CREATE_ISSUE, Permission.UPDATE_ISSUE, Permission.ASSIGN_ISSUE,
        Permission.CREATE_BRANCH, Permission.CREATE_PR, Permission.MERGE_PR,
        Permission.TRIGGER_CI, Permission.ROLLBACK, Permission.RESTART_SERVICE,
        Permission.APPROVE_ACTION, Permission.GENERATE_REPORT,
    },
    Role.developer: {
        Permission.READ_REPOSITORY, Permission.READ_PROJECT, Permission.READ_INCIDENT,
        Permission.CREATE_ISSUE, Permission.CREATE_BRANCH, Permission.CREATE_PR,
        Permission.TRIGGER_CI,
    },
    Role.qa_engineer: {
        Permission.READ_REPOSITORY, Permission.READ_PROJECT, Permission.READ_INCIDENT,
        Permission.CREATE_ISSUE, Permission.TRIGGER_CI,
    },
    Role.devops_engineer: {
        Permission.READ_REPOSITORY, Permission.READ_PROJECT, Permission.READ_INCIDENT,
        Permission.TRIGGER_CI, Permission.DEPLOY_PRODUCTION, Permission.ROLLBACK,
        Permission.RESTART_SERVICE,
    },
    Role.viewer: {
        Permission.READ_REPOSITORY, Permission.READ_PROJECT, Permission.READ_INCIDENT,
    },
    # AI Agent's OWN ceiling — actual runtime permission is
    # min(this set, the requesting user's role permissions). See agent_allowed_permissions().
    Role.ai_agent: {
        Permission.READ_REPOSITORY, Permission.READ_PROJECT, Permission.READ_INCIDENT,
        Permission.CREATE_ISSUE, Permission.UPDATE_ISSUE, Permission.ASSIGN_ISSUE,
        Permission.CREATE_BRANCH, Permission.CREATE_PR, Permission.TRIGGER_CI,
        Permission.SEND_NOTIFICATION, Permission.GENERATE_REPORT,
        # deliberately excluded even from the agent ceiling: MERGE_PR,
        # DEPLOY_PRODUCTION, ROLLBACK, DELETE_DATA - these always require a
        # named human role's explicit action, never an agent's own default.
    },
}


# --- Per-agent tool allow-lists (FR-021 example table) ----------------------------

AGENT_TOOL_PERMISSIONS: dict[str, set[Permission]] = {
    "project_agent": {
        Permission.READ_PROJECT, Permission.CREATE_ISSUE, Permission.UPDATE_ISSUE,
        Permission.ASSIGN_ISSUE, Permission.GENERATE_REPORT,
    },
    "developer_agent": {
        Permission.READ_REPOSITORY, Permission.CREATE_BRANCH, Permission.CREATE_PR,
        Permission.CREATE_ISSUE,
    },
    "incident_agent": {
        Permission.READ_INCIDENT, Permission.READ_REPOSITORY, Permission.CREATE_ISSUE,
        Permission.SEND_NOTIFICATION, Permission.TRIGGER_CI,
        # Note: incident_agent can RECOMMEND a rollback but cannot execute
        # ROLLBACK itself - that stays a high-risk, human-approved action.
    },
    "coordinator_agent": {
        Permission.READ_PROJECT, Permission.READ_REPOSITORY, Permission.READ_INCIDENT,
        Permission.GENERATE_REPORT,
    },
}


@dataclass
class ActionRisk:
    permission: Permission
    level: str  # "low" | "medium" | "high"


# --- Risk classification (FR-022) --------------------------------------------------

RISK_CLASSIFICATION: dict[Permission, str] = {
    Permission.READ_REPOSITORY: "low",
    Permission.READ_PROJECT: "low",
    Permission.READ_INCIDENT: "low",
    Permission.GENERATE_REPORT: "low",
    Permission.CREATE_ISSUE: "medium",
    Permission.UPDATE_ISSUE: "medium",
    Permission.ASSIGN_ISSUE: "medium",
    Permission.CREATE_BRANCH: "medium",
    Permission.CREATE_PR: "medium",
    Permission.SEND_NOTIFICATION: "medium",
    Permission.TRIGGER_CI: "medium",
    Permission.MERGE_PR: "high",
    Permission.DEPLOY_PRODUCTION: "high",
    Permission.ROLLBACK: "high",
    Permission.RESTART_SERVICE: "high",
    Permission.DELETE_DATA: "high",
    Permission.APPROVE_ACTION: "high",
}


def human_has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def agent_allowed_permissions(agent_name: str, acting_on_behalf_of_role: Role) -> set[Permission]:
    """
    The effective permission set for an agent call is the INTERSECTION of:
      - what that specific agent is allowed to do at all (AGENT_TOOL_PERMISSIONS)
      - the AI Agent role ceiling (ROLE_PERMISSIONS[Role.ai_agent])
      - the permissions of the human user the agent is acting for

    This guarantees an agent can never do more than both its own tool
    allow-list AND the requesting user's own role would allow.
    """
    agent_tools = AGENT_TOOL_PERMISSIONS.get(agent_name, set())
    agent_ceiling = ROLE_PERMISSIONS.get(Role.ai_agent, set())
    user_perms = ROLE_PERMISSIONS.get(acting_on_behalf_of_role, set())
    return agent_tools & agent_ceiling & user_perms


def classify_risk(permission: Permission) -> str:
    return RISK_CLASSIFICATION.get(permission, "high")  # unknown action -> fail safe to "high"
