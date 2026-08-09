"""
Unified data model (FR-005).

Every integration adapter normalizes its platform-specific objects (GitHub
Pull Request, Jira Issue, GitHub Actions Workflow Run, Grafana Alert, ...)
into these common entities. Foreign keys between them double as the
"engineering knowledge graph" (FR-006) - e.g. Incident -> Deployment ->
Commit -> Issue can be walked with plain SQL joins, which is enough for
FYP scale and avoids standing up a separate graph database.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Float, Boolean, Enum, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Role(str, enum.Enum):
    system_admin = "system_admin"
    engineering_manager = "engineering_manager"
    tech_lead = "tech_lead"
    developer = "developer"
    qa_engineer = "qa_engineer"
    devops_engineer = "devops_engineer"
    viewer = "viewer"
    ai_agent = "ai_agent"


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    role = Column(Enum(Role), default=Role.viewer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    repositories = relationship("Repository", back_populates="project")
    issues = relationship("Issue", back_populates="project")
    incidents = relationship("Incident", back_populates="project")


class Repository(Base):
    __tablename__ = "repositories"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    provider = Column(String, nullable=False)  # e.g. "github"
    external_id = Column(String, nullable=False)  # provider-native id/slug
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)

    project = relationship("Project", back_populates="repositories")
    commits = relationship("Commit", back_populates="repository")
    pull_requests = relationship("PullRequest", back_populates="repository")


class Commit(Base):
    __tablename__ = "commits"
    id = Column(String, primary_key=True, default=gen_id)
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    sha = Column(String, nullable=False)
    author = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    files_changed = Column(JSON, nullable=True)  # list[str]
    committed_at = Column(DateTime, nullable=True)
    pull_request_id = Column(String, ForeignKey("pull_requests.id"), nullable=True)

    repository = relationship("Repository", back_populates="commits")


class PullRequest(Base):
    __tablename__ = "pull_requests"
    id = Column(String, primary_key=True, default=gen_id)
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    external_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    status = Column(String, nullable=True)  # open / merged / closed
    issue_id = Column(String, ForeignKey("issues.id"), nullable=True)
    additions = Column(Float, nullable=True)
    deletions = Column(Float, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    merged_at = Column(DateTime, nullable=True)

    repository = relationship("Repository", back_populates="pull_requests")
    commits = relationship("Commit", backref="pull_request", foreign_keys=[Commit.pull_request_id])


class Issue(Base):
    __tablename__ = "issues"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    provider = Column(String, nullable=False)  # "jira" / "taiga"
    external_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    status = Column(String, nullable=True)
    assignee = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    sprint = Column(String, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="issues")
    pull_requests = relationship("PullRequest", backref="issue", foreign_keys=[PullRequest.issue_id])


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=gen_id)
    issue_id = Column(String, ForeignKey("issues.id"), nullable=True)
    title = Column(String, nullable=False)
    status = Column(String, nullable=True)
    assignee = Column(String, nullable=True)


class Service(Base):
    __tablename__ = "services"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=True)
    depends_on = Column(JSON, nullable=True)  # list[service_id] - dependency graph (FR-037)


class Build(Base):
    __tablename__ = "builds"
    id = Column(String, primary_key=True, default=gen_id)
    repository_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    provider = Column(String, nullable=False)  # "github_actions"
    external_id = Column(String, nullable=False)
    status = Column(String, nullable=True)  # passed / failed / running
    triggered_by_commit_id = Column(String, ForeignKey("commits.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class Deployment(Base):
    __tablename__ = "deployments"
    id = Column(String, primary_key=True, default=gen_id)
    service_id = Column(String, ForeignKey("services.id"), nullable=False)
    build_id = Column(String, ForeignKey("builds.id"), nullable=True)
    environment = Column(String, nullable=True)
    status = Column(String, nullable=True)
    deployed_at = Column(DateTime, nullable=True)
    rolled_back = Column(Boolean, default=False)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, default=gen_id)
    service_id = Column(String, ForeignKey("services.id"), nullable=True)
    source = Column(String, nullable=True)  # "prometheus" / "simulated"
    severity = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    service_id = Column(String, ForeignKey("services.id"), nullable=True)
    title = Column(String, nullable=False)
    severity = Column(String, nullable=True)
    status = Column(String, default="open")  # open / investigating / resolved
    root_cause_deployment_id = Column(String, ForeignKey("deployments.id"), nullable=True)
    root_cause_confidence = Column(Float, nullable=True)
    evidence = Column(JSON, nullable=True)  # list of {type, id, note}
    opened_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="incidents")


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    title = Column(String, nullable=False)
    source = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String, primary_key=True, default=gen_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    # embedding stored as JSON list[float] for the sqlite/dev path;
    # swap for pgvector's Vector type in the Postgres migration (see README).
    embedding = Column(JSON, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    channel = Column(String, nullable=True)  # "dashboard" / "discord" / "slack"
    role = Column(String, nullable=False)  # "user" / "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentAction(Base):
    __tablename__ = "agent_actions"
    id = Column(String, primary_key=True, default=gen_id)
    agent_name = Column(String, nullable=False)
    action_type = Column(String, nullable=False)  # "create_issue", "trigger_ci", ...
    payload = Column(JSON, nullable=True)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.low)
    status = Column(String, default="pending")  # pending / approved / rejected / executed / failed
    requested_by = Column(String, ForeignKey("users.id"), nullable=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=gen_id)
    actor = Column(String, nullable=False)  # user id or agent name
    action = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    result = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
