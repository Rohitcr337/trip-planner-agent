"""
Tests for llm.py — retry logic, client error handling, caching.

Covers:
- cache hit: second call returns cached response, no API call made
- cache miss: API is called via google-genai Client, response cached, text returned
- timeout & HTTP options: verify 30-second timeout configuration
- retries on timeouts: recovers on retry, or raises after max attempts
- retries on 5xx server errors: recovers on retry, or raises after max attempts
- client errors (400, 401, 403, 404, 429): do NOT retry, raise immediately
  with status code and status text; for 429, include the reported retry delay
- missing API key: RuntimeError raised before any API call
"""
import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
from google.genai import errors


@pytest.fixture(autouse=True)
def isolate_model_quota(tmp_path, monkeypatch):
    from backend.app import quota

    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)


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


class TestRetryableErrors:
    def test_retries_on_timeout_and_succeeds(self, tmp_path, monkeypatch):
        """Should retry on timeout errors and succeed if a later attempt passes."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "Timeout prompt", "gemini-1.5-flash"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "recovered from timeout"
        mock_client.models.generate_content.side_effect = [
            httpx.ReadTimeout("Request timed out after 30s"),
            mock_response,
        ]

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            result = llm_mod.ask(prompt, model)

        assert result == "recovered from timeout"
        assert mock_client.models.generate_content.call_count == 2
        mock_sleep.assert_called_once_with(1)

    def test_retries_on_5xx_server_error_and_succeeds(self, tmp_path, monkeypatch):
        """Should retry on 5xx server errors (like 503 Service Unavailable) and succeed."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "503 prompt", "gemini-1.5-flash"

        server_err = errors.ServerError(
            503,
            {"error": {"code": 503, "message": "Service Unavailable", "status": "UNAVAILABLE"}},
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "recovered from 503"
        mock_client.models.generate_content.side_effect = [server_err, mock_response]

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            result = llm_mod.ask(prompt, model)

        assert result == "recovered from 503"
        assert mock_client.models.generate_content.call_count == 2
        mock_sleep.assert_called_once_with(1)

    def test_fails_after_max_retries_on_persistent_5xx(self, tmp_path, monkeypatch):
        """Fails 3 times (initial + 2 retries) on persistent 5xx and raises RuntimeError."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        prompt, model = "Persistent 500", "gemini-1.5-flash"

        server_err = errors.ServerError(
            500,
            {"error": {"code": 500, "message": "Internal Server Error", "status": "INTERNAL"}},
        )
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = server_err

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError) as exc_info:
                llm_mod.ask(prompt, model)

        err_msg = str(exc_info.value)
        assert "Gemini API call failed after 3 attempts" in err_msg
        assert "500" in err_msg
        assert mock_client.models.generate_content.call_count == 3
        assert mock_sleep.call_count == 2


class TestNonRetryableClientErrors:
    @pytest.mark.parametrize("status_code,status_text,msg", [
        (400, "INVALID_ARGUMENT", "Invalid argument provided"),
        (401, "UNAUTHENTICATED", "Invalid API key"),
        (403, "PERMISSION_DENIED", "Access denied"),
        (404, "NOT_FOUND", "Model not found"),
    ])
    def test_client_errors_do_not_retry_and_raise_immediately(
        self, tmp_path, monkeypatch, status_code, status_text, msg
    ):
        """4xx client errors (400, 401, 403, 404) must raise immediately without retrying."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        client_err = errors.ClientError(
            status_code,
            {"error": {"code": status_code, "message": msg, "status": status_text}},
        )
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = client_err

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError) as exc_info:
                llm_mod.ask("Prompt", "gemini-1.5-flash")

        err_msg = str(exc_info.value)
        assert str(status_code) in err_msg
        assert status_text in err_msg
        # Must NOT retry — called only once, no sleep
        assert mock_client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()

    def test_429_raises_immediately_with_retry_delay_from_details(self, tmp_path, monkeypatch):
        """429 Resource Exhausted must not retry and must include the retry delay in the message."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        resp_json = {
            "error": {
                "code": 429,
                "message": "Resource has been exhausted (e.g. check quota).",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "23.45s",
                    }
                ],
            }
        }
        client_err = errors.ClientError(429, resp_json)
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = client_err

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError) as exc_info:
                llm_mod.ask("Prompt", "gemini-1.5-flash")

        err_msg = str(exc_info.value)
        assert "429" in err_msg
        assert "RESOURCE_EXHAUSTED" in err_msg
        assert "23.45s" in err_msg
        # Must NOT retry
        assert mock_client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()

    def test_429_raises_immediately_with_retry_delay_from_header(self, tmp_path, monkeypatch):
        """429 with Retry-After header must include the delay in the message."""
        import backend.app.llm as llm_mod

        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        resp = httpx.Response(
            429,
            headers={"retry-after": "15"},
            json={"error": {"code": 429, "message": "Rate limit exceeded", "status": "RESOURCE_EXHAUSTED"}},
        )
        client_err = errors.ClientError(429, resp.json(), resp)
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = client_err

        with patch("backend.app.llm.genai.Client", return_value=mock_client), \
             patch("backend.app.llm.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError) as exc_info:
                llm_mod.ask("Prompt", "gemini-1.5-flash")

        err_msg = str(exc_info.value)
        assert "429" in err_msg
        assert "15" in err_msg
        assert mock_client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()


class TestMissingApiKey:
    def test_raises_runtime_error_when_key_missing(self, tmp_path, monkeypatch):
        import backend.app.llm as llm_mod

        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setattr(llm_mod, "_CACHE_DIR", str(tmp_path))

        with pytest.raises(RuntimeError, match="LLM_API_KEY"):
            llm_mod.ask("anything")
