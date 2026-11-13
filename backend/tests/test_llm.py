"""
Tests for llm.py — task 1.2 / SDK update.

Covers:
- cache hit: second call returns cached response, no API call made
- cache miss: API is called via google-genai Client, response cached, text returned
- timeout & HTTP options: verify 30-second timeout configuration
- retries: at most 2 retries on failure before raising RuntimeError with clear message
- missing API key: RuntimeError raised before any API call
"""
import json
import os
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCacheHit:
    def test_returns_cached_response_without_calling_api(self, tmp_path, monkeypatch):
        """
        When a cache file already exists, ask() must return its content
        and must NOT call the Gemini API.
        """
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        # Pre-populate cache
        prompt, model = "Hello", "gemini-1.5-flash"
        key = llm_mod._hash(prompt, model)
        cache_file = tmp_path / f"{key}.json"
        cache_file.write_text(
            json.dumps({"model": model, "prompt": prompt, "response": "cached!"}),
            encoding="utf-8",
        )

        with patch("backend.app.llm.genai.Client") as mock_client_cls:
            result = llm_mod.ask(prompt, model)

        assert result == "cached!"
        mock_client_cls.assert_not_called()

    def test_prints_cache_hit(self, tmp_path, monkeypatch, capsys):
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "Hi", "gemini-1.5-flash"
        key = llm_mod._hash(prompt, model)
        (tmp_path / f"{key}.json").write_text(
            json.dumps({"response": "hi back"}), encoding="utf-8"
        )

        with patch("backend.app.llm.genai.Client"):
            llm_mod.ask(prompt, model)

        captured = capsys.readouterr()
        assert "cache hit" in captured.out


class TestCacheMiss:
    def test_calls_api_and_caches_response(self, tmp_path, monkeypatch):
        """
        On a cache miss, ask() must call the Gemini API via google-genai,
        write the result to cache/<hash>.json, and return the text.
        """
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "What is 2+2?", "gemini-1.5-flash"

        # Mock the google-genai Client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "4"
        mock_client.models.generate_content.return_value = mock_response

        with patch("backend.app.llm.genai.Client", return_value=mock_client) as mock_client_cls:
            result = llm_mod.ask(prompt, model)

        assert result == "4"

        # Client was initialized with correct key and 30s timeout (30,000 ms)
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["http_options"].timeout == 30_000

        # generate_content was called on models
        mock_client.models.generate_content.assert_called_once_with(
            model=model,
            contents=prompt,
        )

        # Cache file must now exist
        key = llm_mod._hash(prompt, model)
        cache_file = tmp_path / f"{key}.json"
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        assert cached["response"] == "4"
        assert cached["model"] == model

    def test_second_call_uses_cache(self, tmp_path, monkeypatch):
        """Second call for the same prompt must be a cache hit (no API call)."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "Repeat", "gemini-1.5-flash"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "once"
        mock_client.models.generate_content.return_value = mock_response

        with patch("backend.app.llm.genai.Client", return_value=mock_client):
            first = llm_mod.ask(prompt, model)
            second = llm_mod.ask(prompt, model)

        assert first == second == "once"
        # generate_content called exactly once (second call hits cache)
        mock_client.models.generate_content.assert_called_once()


class TestRetriesAndErrors:
    def test_retries_on_failure_and_succeeds(self, tmp_path, monkeypatch):
        """Should retry on transient failure up to 2 times and succeed if an attempt passes."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "Flaky prompt", "gemini-1.5-flash"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "recovered"
        # Fail once, then succeed on second attempt (1st retry)
        mock_client.models.generate_content.side_effect = [
            RuntimeError("Temporary network glitch"),
            mock_response,
        ]

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            result = llm_mod.ask(prompt, model)

        assert result == "recovered"
        assert mock_client.models.generate_content.call_count == 2
        mock_sleep.assert_called_once_with(1)

    def test_raises_after_max_retries_exceeded(self, tmp_path, monkeypatch):
        """Fails 3 times (initial + 2 retries) and raises RuntimeError with clear message."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "Failing prompt", "gemini-1.5-flash"

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ConnectionError("Connection timed out")

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError) as exc_info:
                llm_mod.ask(prompt, model)

        err_msg = str(exc_info.value)
        assert "Gemini API call failed after 3 attempts" in err_msg
        assert "Connection timed out" in err_msg
        assert mock_client.models.generate_content.call_count == 3
        assert mock_sleep.call_count == 2


class TestMissingApiKey:
    def test_raises_runtime_error_when_key_missing(self, tmp_path, monkeypatch):
        import backend.app.llm as llm_mod

        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        with pytest.raises(RuntimeError, match="LLM_API_KEY"):
            llm_mod.ask("anything")
