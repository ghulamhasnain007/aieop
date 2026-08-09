"""
Conversation memory (FR-025).

Generalizes the original per-channel memory into layered scopes:
  - conversation memory: turn-by-turn history for pronoun/reference resolution
    ("What did you find?" -> resolves "you"/"the issue" from recent turns)
  - user memory: facts that persist across a user's sessions
  - project memory: facts scoped to a project regardless of who's asking

Incident memory and agent-task memory are intentionally deferred to Phase 4
(they need the Incident/Agent tables populated by real agent runs first).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import Conversation


class ConversationMemory:
    def __init__(self, db: Session, project_id: str | None, user_id: str | None, channel: str = "dashboard"):
        self.db = db
        self.project_id = project_id
        self.user_id = user_id
        self.channel = channel

    def append(self, role: str, content: str) -> Conversation:
        entry = Conversation(
            user_id=self.user_id,
            project_id=self.project_id,
            channel=self.channel,
            role=role,
            content=content,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def recent(self, limit: int = 10) -> list[Conversation]:
        query = self.db.query(Conversation).filter(Conversation.channel == self.channel)
        if self.project_id:
            query = query.filter(Conversation.project_id == self.project_id)
        if self.user_id:
            query = query.filter(Conversation.user_id == self.user_id)
        return list(reversed(query.order_by(Conversation.created_at.desc()).limit(limit).all()))

    def as_prompt_context(self, limit: int = 10) -> str:
        """Render recent turns as a compact string suitable for feeding to an
        LLM prompt, so 'What did you find?' can resolve against prior turns."""
        turns = self.recent(limit=limit)
        return "\n".join(f"{t.role}: {t.content}" for t in turns)
