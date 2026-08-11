"""
Coordinator Agent (FR-009).

Understands the request (via intent_classifier), selects the appropriate
sub-agent(s), executes them, and assembles a final answer. Phase-1/4
implementation routes on (intent, domain) with simple keyword extraction
for IDs; this is the seam where a LangGraph state machine replaces the
if/elif routing once multi-step, multi-agent requests are needed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.agents.intent_classifier import classify_intent, IntentResult
from app.agents.project_agent import ProjectAgent
from app.agents.developer_agent import DeveloperAgent
from app.agents.incident_agent import IncidentAgent
from app.knowledge.rag_service import RagService
from app.llm.narrate import narrate_root_cause
from app.memory.conversation_memory import ConversationMemory
from app.models.entities import Role
from app.rbac.permissions import agent_allowed_permissions, Permission


@dataclass
class CoordinatorResponse:
    intent: IntentResult
    agent_used: str | None
    answer: str
    evidence: list[dict] = field(default_factory=list)
    requires_clarification: bool = False
    low_confidence_threshold: float = 0.55


class CoordinatorAgent:
    name = "coordinator_agent"

    def __init__(self, db: Session, low_confidence_threshold: float = 0.55):
        self.db = db
        self.low_confidence_threshold = low_confidence_threshold

    def handle(
        self,
        message: str,
        project_id: str | None,
        user_role: Role,
        memory: ConversationMemory | None = None,
    ) -> CoordinatorResponse:
        intent = classify_intent(message)

        if memory:
            memory.append(role="user", content=message)

        # FR-008: low-confidence requests trigger clarification, not a guess.
        if intent.confidence < self.low_confidence_threshold:
            response = CoordinatorResponse(
                intent=intent,
                agent_used=None,
                answer="I'm not confident what you're asking for. Could you rephrase, or specify "
                       "a project, sprint, service, or PR number?",
                requires_clarification=True,
            )
            if memory:
                memory.append(role="assistant", content=response.answer)
            return response

        agent_name = self._domain_to_agent(intent.domain)
        allowed = agent_allowed_permissions(agent_name, user_role) if agent_name else set()

        answer, evidence = self._dispatch(intent, message, project_id, allowed)

        response = CoordinatorResponse(
            intent=intent,
            agent_used=agent_name,
            answer=answer,
            evidence=evidence,
        )
        if memory:
            memory.append(role="assistant", content=answer)
        return response

    # -- internal routing --------------------------------------------------

    @staticmethod
    def _domain_to_agent(domain: str) -> str | None:
        return {
            "project": "project_agent",
            "developer": "developer_agent",
            "incident": "incident_agent",
        }.get(domain)

    def _dispatch(
        self, intent: IntentResult, message: str, project_id: str | None, allowed: set[Permission]
    ) -> tuple[str, list[dict]]:
        if intent.domain == "project" and project_id:
            if Permission.READ_PROJECT not in allowed:
                return "You don't have permission to view project data.", []
            agent = ProjectAgent(self.db)
            sprint = self._extract_sprint(message) or "current"
            result = agent.sprint_risk(project_id, sprint)
            answer = (
                f"Sprint '{result.sprint}': {result.completed_tasks}/{result.total_tasks} tasks complete, "
                f"{result.overdue_tasks} overdue. Estimated completion probability: "
                f"{int(result.completion_probability * 100)}%."
            )
            if result.risk_factors:
                answer += " Risk factors: " + "; ".join(result.risk_factors) + "."
            return answer, [{"type": "sprint_data", "sprint": result.sprint}]

        if intent.domain == "developer":
            if Permission.READ_REPOSITORY not in allowed:
                return "You don't have permission to view repository data.", []
            repo_id = self._extract_repo_id(message)
            if not repo_id:
                return "Which repository should I look at? Please provide a repository ID.", []
            agent = DeveloperAgent(self.db)
            result = agent.summarize_recent_changes(repo_id)
            answer = f"Recent changes in {result.repository}: {len(result.pull_requests)} PR(s), " \
                     f"{len(result.commits)} commit(s)."
            if result.potential_concerns:
                answer += " Potential concerns: " + "; ".join(result.potential_concerns) + "."
            return answer, [{"type": "pull_request", "id": p["id"]} for p in result.pull_requests]

        if intent.domain == "incident":
            if Permission.READ_INCIDENT not in allowed:
                return "You don't have permission to view incident data.", []
            service_id = self._extract_service_id(message)
            if not service_id:
                return "Which service is affected? Please provide a service ID.", []
            agent = IncidentAgent(self.db)
            result = agent.investigate(service_id, incident_title=message)
            if result.insufficient_evidence:
                return result.recommendation or "Insufficient evidence to determine a root cause.", \
                    [e.__dict__ for e in result.evidence]
            narrated = narrate_root_cause(result)
            answer = narrated or (
                f"Likely cause: {result.likely_cause} (confidence: {int(result.confidence * 100)}%). "
                f"{result.recommendation}"
            )
            return answer, [e.__dict__ for e in result.evidence]

        if intent.domain == "general" and intent.intent in {"query", "search", "summarize"}:
            rag = RagService(self.db)
            result = rag.query(message, project_id=project_id)
            evidence = [
                {"type": "fact", "source": "document", "id": s.chunk_id, "detail": f"{s.document_title} (score {s.score})"}
                for s in result.sources
            ]
            return result.answer, evidence

        return "I understood your request but no specialized agent is wired up for this yet.", []

    _UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

    @staticmethod
    def _extract_sprint(text: str) -> str | None:
        m = re.search(r"sprint\s+([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else None

    @classmethod
    def _extract_repo_id(cls, text: str) -> str | None:
        # Prefer an explicit UUID anywhere in the message (dashboard passes
        # real entity IDs this way); fall back to a labelled "repo: <token>".
        uuid_match = re.search(cls._UUID_RE, text)
        if uuid_match:
            return uuid_match.group(0)
        m = re.search(r"repo(?:sitory)?[:\s]+([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else None

    @classmethod
    def _extract_service_id(cls, text: str) -> str | None:
        uuid_match = re.search(cls._UUID_RE, text)
        if uuid_match:
            return uuid_match.group(0)
        m = re.search(r"service[:\s]+([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else None
