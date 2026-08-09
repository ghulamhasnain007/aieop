"""
Intent classification (FR-008).

Phase-1 implementation is a fast, deterministic rule-based classifier -
cheap, testable, and good enough to route the majority of demo queries.
It returns the exact schema from the requirements doc. Swap
`classify_intent` internals for an LLM call (Gemini via LangChain) later
without changing the return contract or any caller.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict


VALID_INTENTS = {
    "query", "search", "analyze", "create", "update", "delete",
    "investigate", "summarize", "predict", "recommend", "execute", "report",
}

VALID_DOMAINS = {"project", "developer", "incident", "general"}


@dataclass
class IntentResult:
    intent: str
    domain: str
    confidence: float
    requires_write: bool
    risk_level: str  # "low" | "medium" | "high"

    def to_dict(self) -> dict:
        return asdict(self)


# (regex pattern, intent, domain, base_confidence)
_RULES: list[tuple[str, str, str, float]] = [
    (r"\bwhy did\b.*\bfail", "investigate", "incident", 0.9),
    (r"\binvestigat", "investigate", "incident", 0.88),
    (r"\bincident\b|\boutage\b", "investigate", "incident", 0.8),
    (r"\bcreate\b.*\bissue\b", "create", "project", 0.9),
    (r"\bassign\b", "update", "project", 0.85),
    (r"\bsummar", "summarize", "general", 0.85),
    (r"\bwill we finish\b|\bcompletion probability\b|\bsprint.*(risk|finish)\b", "predict", "project", 0.85),
    (r"\bwhat changed\b|\bcode change\b|\bpull request\b|\bpr #\d+", "analyze", "developer", 0.8),
    (r"\bfind\b|\bsearch\b|\bshow me\b", "search", "general", 0.7),
    (r"\brecommend", "recommend", "general", 0.8),
    (r"\breport\b", "report", "general", 0.75),
    (r"\bdelete\b", "delete", "general", 0.85),
    (r"\btrigger\b.*\b(pipeline|ci|build)\b|\bdeploy\b|\brollback\b|\bmerge\b", "execute", "developer", 0.85),
]

_WRITE_INTENTS = {"create", "update", "delete", "execute"}
_HIGH_RISK_KEYWORDS = re.compile(r"\bdeploy\b|\brollback\b|\bmerge\b|\bdelete\b", re.IGNORECASE)
_MEDIUM_RISK_INTENTS = {"create", "update"}


def classify_intent(text: str) -> IntentResult:
    lowered = text.lower().strip()

    best: tuple[str, str, float] | None = None
    for pattern, intent, domain, confidence in _RULES:
        if re.search(pattern, lowered):
            if best is None or confidence > best[2]:
                best = (intent, domain, confidence)

    if best is None:
        intent, domain, confidence = "query", "general", 0.5
    else:
        intent, domain, confidence = best

    requires_write = intent in _WRITE_INTENTS

    if _HIGH_RISK_KEYWORDS.search(lowered):
        risk_level = "high"
    elif intent in _MEDIUM_RISK_INTENTS:
        risk_level = "medium"
    else:
        risk_level = "low"

    return IntentResult(
        intent=intent,
        domain=domain,
        confidence=round(confidence, 2),
        requires_write=requires_write,
        risk_level=risk_level,
    )
