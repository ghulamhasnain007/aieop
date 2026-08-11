"""
LLM client (Anthropic Claude).

CRITICAL DESIGN RULE: this client only ever PHRASES facts that the caller
already gathered and passed in - it never has DB access, never calls
tools, and every prompt built on top of it must include an explicit
instruction not to state anything beyond the provided evidence. The
deterministic agents (Incident/Project/Developer) remain the source of
truth for what happened; the LLM's job is fluent natural-language
synthesis of that evidence, not independent reasoning about facts it
wasn't given.

Every caller must have a deterministic fallback (extractive text,
template string, etc.) for when no API key is configured - see
app.knowledge.rag_service and app.agents.coordinator for the two places
this is used. The platform must remain fully functional, just less
fluent, without an API key.
"""
from __future__ import annotations

import httpx

from app.config.config import settings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class LLMError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.anthropic_api_key)


def generate(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
    """Single-turn completion. Raises LLMError on any failure - callers
    must catch this and fall back to their deterministic behavior rather
    than letting a request fail outright over an LLM hiccup."""
    if not settings.anthropic_api_key:
        raise LLMError("No ANTHROPIC_API_KEY configured")

    try:
        resp = httpx.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        if not text:
            raise LLMError("Empty response from Anthropic API")
        return text.strip()
    except httpx.HTTPError as exc:
        raise LLMError(f"Anthropic API request failed: {exc}") from exc
