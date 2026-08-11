"""
Provider-agnostic LLM client.

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
app.knowledge.rag_service and app.llm.narrate. The platform must remain
fully functional, just less fluent, without an LLM key.

Provider selection (LLM_PROVIDER env var, default "gemini"):
  - "gemini"    -> app.llm.providers.gemini.GeminiProvider (default -
                   free tier available, get a key at
                   https://aistudio.google.com/apikey)
  - "anthropic" -> app.llm.providers.anthropic.AnthropicProvider

LLM_API_KEY and LLM_MODEL apply to whichever provider is selected - swap
providers by changing LLM_PROVIDER, no code changes needed.
"""
from __future__ import annotations

from app.config.config import settings
from app.llm.errors import LLMError
from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.anthropic import AnthropicProvider

_PROVIDERS = {
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
}


def is_configured() -> bool:
    return bool(settings.llm_api_key)


def _build_provider():
    provider_name = (settings.llm_provider or "gemini").lower()
    provider_cls = _PROVIDERS.get(provider_name)
    if not provider_cls:
        raise LLMError(
            f"Unknown LLM_PROVIDER '{provider_name}' - supported: {', '.join(_PROVIDERS)}"
        )
    return provider_cls(api_key=settings.llm_api_key, model=settings.llm_model)


def generate(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
    """Single-turn completion via whichever provider is configured. Raises
    LLMError on any failure - callers must catch this and fall back to
    their deterministic behavior rather than letting a request fail
    outright over an LLM hiccup."""
    if not settings.llm_api_key:
        raise LLMError("No LLM_API_KEY configured")

    provider = _build_provider()
    return provider.generate(system_prompt, user_prompt, max_tokens)
