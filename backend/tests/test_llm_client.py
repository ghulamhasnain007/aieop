from unittest.mock import patch, MagicMock

import pytest

from app.llm import client as llm_client
from app.llm.client import generate, is_configured, LLMError


def test_not_configured_without_api_key(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", None)
    assert is_configured() is False


def test_configured_with_api_key(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "sk-test-123")
    assert is_configured() is True


def test_generate_raises_without_key(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", None)
    with pytest.raises(LLMError):
        generate("system prompt", "user prompt")


def test_generate_returns_text_on_success(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "sk-test-123")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"content": [{"type": "text", "text": "The answer is 42."}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = generate("system", "user")

    assert result == "The answer is 42."
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["x-api-key"] == "sk-test-123"


def test_generate_raises_llm_error_on_http_failure(monkeypatch):
    import httpx
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "sk-test-123")

    with patch("httpx.post", side_effect=httpx.HTTPError("connection failed")):
        with pytest.raises(LLMError):
            generate("system", "user")
