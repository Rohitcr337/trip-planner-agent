"""
llm.py — single entry point for all model calls.

ask(prompt, model) hashes model+prompt, checks cache/<hash>.json,
returns the cached text if present ("cache hit"), otherwise calls
the Google Gemini API via the google-genai SDK (HTTP, not gRPC),
persists the response, and returns it.

All model calls in this project MUST go through ask().

Timeout: 30 seconds per attempt.
Retries: up to 2 retries on transient errors, then raises RuntimeError
         with a clear message.
"""
import hashlib
import json
import os
import time

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
_DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache")

_TIMEOUT_MS = 30_000   # 30 seconds in milliseconds
_MAX_RETRIES = 2       # number of retry attempts after the first failure


def _cache_path(key: str) -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"{key}.json")


def _hash(prompt: str, model: str) -> str:
    payload = json.dumps({"model": model, "prompt": prompt}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _call_api(prompt: str, model: str, api_key: str) -> str:
    """
    Make one attempt to call the Gemini API via google-genai (HTTP).
    Uses an HTTP client (no gRPC) with a 30-second timeout.
    Raises Exception on failure.
    """
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=_TIMEOUT_MS),
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text


# ── Public API ────────────────────────────────────────────────────────────────

def ask(prompt: str, model: str | None = None) -> str:
    """
    Call the LLM and return the text response.

    Checks the disk cache first; on a miss, calls the Gemini API with up to
    _MAX_RETRIES retries, writes the result to cache, and returns it.

    Args:
        prompt: The full prompt string.
        model:  The Gemini model name (defaults to LLM_MODEL env var or gemini-1.5-flash).

    Returns:
        The model's text response as a plain string.

    Raises:
        RuntimeError: If LLM_API_KEY is not set, or if all retry attempts fail.
    """
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY environment variable is not set.")

    chosen_model = model if model is not None else os.getenv("LLM_MODEL", _DEFAULT_MODEL)

    key = _hash(prompt, chosen_model)
    path = _cache_path(key)

    # ── Cache hit ─────────────────────────────────────────────────────────
    if os.path.exists(path):
        print("cache hit")
        with open(path, encoding="utf-8") as f:
            return json.load(f)["response"]

    # ── Live call with retries ─────────────────────────────────────────────
    last_exc: Exception | None = None
    text: str | None = None
    elapsed: float = 0.0

    for attempt in range(1, _MAX_RETRIES + 2):   # attempts: 1, 2, 3
        try:
            t0 = time.perf_counter()
            text = _call_api(prompt, chosen_model, api_key)
            elapsed = time.perf_counter() - t0
            break
        except Exception as exc:
            last_exc = exc
            if attempt <= _MAX_RETRIES:
                time.sleep(attempt)
            else:
                raise RuntimeError(
                    f"Gemini API call failed after {_MAX_RETRIES + 1} attempts. "
                    f"Last error: {exc}"
                ) from exc

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"model": chosen_model, "prompt": prompt, "response": text, "elapsed_s": elapsed},
            f,
            ensure_ascii=False,
            indent=2,
        )

    return text
