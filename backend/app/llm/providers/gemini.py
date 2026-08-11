"""
Google Gemini provider (default - has a generous free tier, no billing
setup required to get started). Get a key at https://aistudio.google.com/apikey
"""
from __future__ import annotations

import httpx

from app.llm.errors import LLMError
from app.llm.providers.base import LLMProvider

DEFAULT_MODEL = "gemini-2.0-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        model = self.model or DEFAULT_MODEL
        url = f"{API_BASE}/models/{model}:generateContent"

        try:
            resp = httpx.post(
                url,
                params={"key": self.api_key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "generationConfig": {"maxOutputTokens": max_tokens},
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini API request failed: {exc}") from exc

        candidates = data.get("candidates") or []
        if not candidates:
            # e.g. blocked by safety filters - promptFeedback carries the reason
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise LLMError(f"Gemini returned no candidates{f' (blocked: {reason})' if reason else ''}")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise LLMError("Empty response from Gemini API")
        return text
