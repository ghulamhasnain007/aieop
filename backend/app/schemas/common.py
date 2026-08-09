from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    project_id: str | None = None
    channel: str = "dashboard"


class ChatResponse(BaseModel):
    intent: str
    domain: str
    confidence: float
    risk_level: str
    agent_used: str | None
    answer: str
    evidence: list[dict]
    requires_clarification: bool


class IntegrationHealthItem(BaseModel):
    provider: str
    connected: bool
    detail: str


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
