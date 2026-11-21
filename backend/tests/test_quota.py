from unittest.mock import patch

import pytest

from backend.app import quota
from backend.app import llm


def test_quota_counts_real_attempts_but_not_cache_hits(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path / "quota")
    monkeypatch.setattr(quota, "MAX_MODEL_CALLS_PER_DAY", 2)
    monkeypatch.setattr(llm, "_CACHE_DIR", str(tmp_path / "responses"))
    with patch("backend.app.llm._call_api", return_value="answer") as api:
        assert llm.ask("one", "test-model") == "answer"
        assert llm.ask("one", "test-model") == "answer"
        assert quota.get_model_call_count() == 1
        assert llm.ask("two", "test-model") == "answer"
        assert quota.get_model_call_count() == 2
        with pytest.raises(quota.ModelCallLimitReached):
            llm.ask("three", "test-model")
    assert api.call_count == 2
