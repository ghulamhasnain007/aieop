"""
LLMProvider - the interface every backend (Gemini, Anthropic, ...)
implements. app.llm.client selects one based on settings.llm_provider and
calls it through this same interface, so RAG synthesis and incident
narration never need to know which provider is actually configured.
"""
from __future__ import annotations

import abc


class LLMProvider(abc.ABC):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abc.abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Returns the generated text, or raises app.llm.errors.LLMError."""
