"""
Anthropic Claude provider (alternative to the default Gemini backend).
"""
from __future__ import annotations

import httpx

from app.llm.errors import LLMError
from app.llm.providers.base import LLMProvider

DEFAULT_MODEL = "claude-sonnet-5"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        model = self.model or DEFAULT_MODEL

        try:
            resp = httpx.post(
                API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Anthropic API request failed: {exc}") from exc

        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        ).strip()
        if not text:
            raise LLMError("Empty response from Anthropic API")
        return text
