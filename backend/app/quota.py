"""Daily cap for actual outbound language-service requests."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_MODEL_CALLS_PER_DAY = 15
CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
_quota_lock = threading.Lock()


class ModelCallLimitReached(RuntimeError):
    """Raised before an outbound request would exceed the daily cap."""


def _quota_path() -> Path:
    today = datetime.now(timezone.utc).date().isoformat()
    return CACHE_DIR / f"model_calls_{today}.json"


def _read_count(path: Path) -> int:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(content.get("count", 0)))
    except FileNotFoundError:
        return 0
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("Could not read model call counter; starting at zero: %s", exc)
        return 0


def get_model_call_count() -> int:
    with _quota_lock:
        return _read_count(_quota_path())


def limit_reached() -> bool:
    return get_model_call_count() >= MAX_MODEL_CALLS_PER_DAY


def record_model_call() -> None:
    """Count one real outbound attempt, raising when the daily cap is reached."""
    with _quota_lock:
        path = _quota_path()
        count = _read_count(path)
        if count >= MAX_MODEL_CALLS_PER_DAY:
            raise ModelCallLimitReached("Daily model call limit reached. Try again tomorrow.")
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"count": count + 1}), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not persist model call counter: %s", exc)
            raise RuntimeError("Model call limit could not be checked. Please retry later.") from exc
