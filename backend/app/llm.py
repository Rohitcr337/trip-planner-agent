"""
llm.py — single entry point for all model calls.

ask(prompt, model) hashes model+prompt, checks cache/<hash>.json,
returns the cached text if present ("cache hit"), otherwise calls
the Google Gemini API via the google-genai SDK (HTTP, not gRPC),
persists the response, and returns it.

All model calls in this project MUST go through ask().

Timeout: 30 seconds per attempt.
Retries: at most 2 retries on timeouts and 5xx server errors only.
         Client errors (4xx, including 400, 401, 403, 404, 429) are NOT retried
         and raise immediately with status and retry delay (for 429).
"""
import hashlib
import json
import os
import re
import time

import httpx
from google import genai
from google.genai import errors, types
from dotenv import load_dotenv
from backend.app.quota import ModelCallLimitReached, record_model_call

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


def _get_status_code(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    resp = getattr(exc, "response", None)
    if resp and hasattr(resp, "status_code") and isinstance(resp.status_code, int):
        return resp.status_code
    return None


def _get_status_text(exc: Exception) -> str:
    status = getattr(exc, "status", None)
    if status:
        return str(status)
    code = _get_status_code(exc)
    if code:
        return f"HTTP {code}"
    return "UNKNOWN_STATUS"


def _extract_retry_delay(exc: Exception) -> str | None:
    """Extract retry delay string from response headers, RetryInfo details, or message."""
    # 1. From response headers (retry-after)
    resp = getattr(exc, "response", None)
    if resp and hasattr(resp, "headers"):
        headers = resp.headers
        ra = headers.get("retry-after") or headers.get("Retry-After")
        if ra:
            return str(ra)

    # 2. From details (e.g. google.rpc.RetryInfo)
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        sub_details = (
            details.get("error", {}).get("details")
            or details.get("details")
            or []
        )
        if isinstance(sub_details, list):
            for item in sub_details:
                if isinstance(item, dict) and "retryDelay" in item:
                    return str(item["retryDelay"])

    # 3. From message regex, e.g. "retry in 18s" or "retry after 18.2s"
    msg = str(getattr(exc, "message", None) or exc)
    m = re.search(r"retry (?:in|after) ([0-9]+(?:\.[0-9]+)?s?)", msg, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def _is_client_error(exc: Exception) -> bool:
    if isinstance(exc, errors.ClientError):
        return True
    code = _get_status_code(exc)
    if code is not None and 400 <= code < 500:
        return True
    return False


def _is_retryable_error(exc: Exception) -> bool:
    """Retry only on timeouts and 5xx server errors."""
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return True
    if isinstance(exc, errors.ServerError):
        return True
    code = _get_status_code(exc)
    if code is not None and 500 <= code < 600:
        return True
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    if "timeout" in exc_str or "timed out" in exc_str or "timeout" in exc_type:
        return True
    return False


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

    Checks the disk cache first; on a miss, calls the Gemini API.
    Retries up to _MAX_RETRIES on timeouts and 5xx server errors only.
    Client errors (4xx) raise immediately without retrying.

    Args:
        prompt: The full prompt string.
        model:  The Gemini model name (defaults to LLM_MODEL env var or gemini-1.5-flash).

    Returns:
        The model's text response as a plain string.

    Raises:
        RuntimeError: If LLM_API_KEY is not set, if client error occurs, or if retries fail.
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
    text: str | None = None
    elapsed: float = 0.0

    for attempt in range(1, _MAX_RETRIES + 2):   # attempts: 1, 2, 3
        try:
            t0 = time.perf_counter()
            record_model_call()
            text = _call_api(prompt, chosen_model, api_key)
            elapsed = time.perf_counter() - t0
            break
        except Exception as exc:
            if isinstance(exc, ModelCallLimitReached):
                raise
            # 1. 4xx Client errors: do NOT retry, raise immediately
            if _is_client_error(exc):
                code = _get_status_code(exc) or "4xx"
                status_text = _get_status_text(exc)
                if code == 429:
                    delay = _extract_retry_delay(exc)
                    delay_msg = f" Retry delay: {delay}." if delay else " Retry delay not specified."
                    raise RuntimeError(
                        f"Gemini API client error: status {code} ({status_text}).{delay_msg} {exc}"
                    ) from exc
                raise RuntimeError(
                    f"Gemini API client error: status {code} ({status_text}). {exc}"
                ) from exc

            # 2. Check if error is retryable (timeout or 5xx server error)
            if not _is_retryable_error(exc):
                raise RuntimeError(f"Gemini API error (non-retryable): {exc}") from exc

            # 3. Retryable error (timeout or 5xx): retry up to _MAX_RETRIES
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
