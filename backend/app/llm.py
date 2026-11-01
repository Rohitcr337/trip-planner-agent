"""
llm.py — single entry point for all model calls.

ask(prompt, model) hashes model+prompt, checks cache/<hash>.json,
returns the cached text if present ("cache hit"), otherwise calls
the Google Gemini API, persists the response, and returns it.

All model calls in this project MUST go through ask().
"""
import hashlib
import json
import os
import time

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
_DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache")


def _cache_path(key: str) -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"{key}.json")


def _hash(prompt: str, model: str) -> str:
    payload = json.dumps({"model": model, "prompt": prompt}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── Public API ────────────────────────────────────────────────────────────────

def ask(prompt: str, model: str = _DEFAULT_MODEL) -> str:
    """
    Call the LLM and return the text response.

    Checks the disk cache first; on a miss, calls the Gemini API,
    writes the result to cache, and returns it.

    Args:
        prompt: The full prompt string.
        model:  The Gemini model name (defaults to LLM_MODEL env var).

    Returns:
        The model's text response as a plain string.

    Raises:
        RuntimeError: If LLM_API_KEY is not set.
    """
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY environment variable is not set.")

    key = _hash(prompt, model)
    path = _cache_path(key)

    # ── Cache hit ─────────────────────────────────────────────────────────
    if os.path.exists(path):
        print("cache hit")
        with open(path, encoding="utf-8") as f:
            return json.load(f)["response"]

    # ── Live call ─────────────────────────────────────────────────────────
    genai.configure(api_key=api_key)
    t0 = time.perf_counter()
    gemini_model = genai.GenerativeModel(model)
    result = gemini_model.generate_content(prompt)
    elapsed = time.perf_counter() - t0

    text = result.text
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"model": model, "prompt": prompt, "response": text, "elapsed_s": elapsed},
            f,
            ensure_ascii=False,
            indent=2,
        )

    return text
