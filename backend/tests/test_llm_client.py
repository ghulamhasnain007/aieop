from unittest.mock import patch, MagicMock

import pytest

from app.llm import client as llm_client
from app.llm.client import generate, is_configured
from app.llm.errors import LLMError


def test_not_configured_without_api_key(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_api_key", None)
    assert is_configured() is False


def test_configured_with_api_key(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "some-key")
    assert is_configured() is True


def test_generate_raises_without_key(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_api_key", None)
    with pytest.raises(LLMError):
        generate("system", "user")


def test_defaults_to_gemini_provider(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "gem-key")
    monkeypatch.setattr(llm_client.settings, "llm_model", None)

    provider = llm_client._build_provider()
    assert isinstance(provider, llm_client.GeminiProvider)


def test_selects_anthropic_provider_when_configured(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "sk-key")
    monkeypatch.setattr(llm_client.settings, "llm_model", None)

    provider = llm_client._build_provider()
    assert isinstance(provider, llm_client.AnthropicProvider)


def test_unknown_provider_raises_llm_error(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "some-unknown-llm")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "key")
    with pytest.raises(LLMError, match="Unknown LLM_PROVIDER"):
        generate("system", "user")


def test_gemini_generate_returns_text_on_success(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "gem-key")
    monkeypatch.setattr(llm_client.settings, "llm_model", None)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "The answer is 42."}]}}]
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = generate("system", "user")

    assert result == "The answer is 42."
    assert mock_post.call_args.kwargs["params"]["key"] == "gem-key"
    assert "gemini-2.0-flash" in mock_post.call_args.args[0]


def test_gemini_raises_on_blocked_response(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "gem-key")
    monkeypatch.setattr(llm_client.settings, "llm_model", None)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}

    with patch("httpx.post", return_value=mock_response):
        with pytest.raises(LLMError, match="SAFETY"):
            generate("system", "user")


def test_anthropic_generate_returns_text_on_success(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "sk-key")
    monkeypatch.setattr(llm_client.settings, "llm_model", None)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"content": [{"type": "text", "text": "Hello from Claude."}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = generate("system", "user")

    assert result == "Hello from Claude."
    assert mock_post.call_args.kwargs["headers"]["x-api-key"] == "sk-key"


def test_custom_model_override_is_respected(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "gem-key")
    monkeypatch.setattr(llm_client.settings, "llm_model", "gemini-1.5-pro")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        generate("system", "user")

    assert "gemini-1.5-pro" in mock_post.call_args.args[0]


def test_generate_raises_llm_error_on_http_failure(monkeypatch):
    import httpx
    monkeypatch.setattr(llm_client.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "gem-key")

    with patch("httpx.post", side_effect=httpx.HTTPError("connection failed")):
        with pytest.raises(LLMError):
            generate("system", "user")
