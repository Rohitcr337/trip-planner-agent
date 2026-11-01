"""
Tests for llm.py — task 1.2.

Covers:
- cache hit: second call returns cached response, no API call made
- cache miss: API is called, response cached, text returned
- missing API key: RuntimeError raised before any API call
"""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ask(tmp_cache: str):
    """
    Return a patched version of ask() that uses a temporary cache directory.
    """
    import importlib
    import backend.app.llm as llm_mod

    # Point the module's cache dir at our temp dir for this test.
    original_cache = llm_mod._CACHE_DIR
    llm_mod._CACHE_DIR = tmp_cache
    yield llm_mod.ask
    llm_mod._CACHE_DIR = original_cache


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

        with patch("google.generativeai.GenerativeModel") as mock_gm:
            result = llm_mod.ask(prompt, model)

        assert result == "cached!"
        mock_gm.assert_not_called()

    def test_prints_cache_hit(self, tmp_path, monkeypatch, capsys):
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "Hi", "gemini-1.5-flash"
        key = llm_mod._hash(prompt, model)
        (tmp_path / f"{key}.json").write_text(
            json.dumps({"response": "hi back"}), encoding="utf-8"
        )

        with patch("google.generativeai.GenerativeModel"):
            llm_mod.ask(prompt, model)

        captured = capsys.readouterr()
        assert "cache hit" in captured.out


class TestCacheMiss:
    def test_calls_api_and_caches_response(self, tmp_path, monkeypatch):
        """
        On a cache miss, ask() must call the Gemini API, write the result
        to cache/<hash>.json, and return the text.
        """
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "What is 2+2?", "gemini-1.5-flash"

        # Mock the Gemini client
        mock_response = MagicMock()
        mock_response.text = "4"
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = mock_response

        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel", return_value=mock_model_instance):
            result = llm_mod.ask(prompt, model)

        assert result == "4"

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
        mock_response = MagicMock()
        mock_response.text = "once"
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = mock_response

        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel", return_value=mock_model_instance):
            first = llm_mod.ask(prompt, model)
            second = llm_mod.ask(prompt, model)

        assert first == second == "once"
        # generate_content called exactly once (second call hits cache)
        mock_model_instance.generate_content.assert_called_once()


class TestMissingApiKey:
    def test_raises_runtime_error_when_key_missing(self, tmp_path, monkeypatch):
        import backend.app.llm as llm_mod

        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        with pytest.raises(RuntimeError, match="LLM_API_KEY"):
            llm_mod.ask("anything")
