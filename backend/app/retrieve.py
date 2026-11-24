"""Lazy retrieval from the persisted local guide index."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.app.vector_store import NumpyStore, TfidfEmbedder

logger = logging.getLogger(__name__)

class IndexMissingError(RuntimeError):
    """Raised when the travel guide index directory is missing."""
    pass


ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = ROOT / "index"
MIN_SIMILARITY = 0.1

_embedder: TfidfEmbedder | None = None
_store: NumpyStore | None = None


def _load_index() -> tuple[TfidfEmbedder, NumpyStore] | None:
    global _embedder, _store
    if _embedder is not None and _store is not None:
        return _embedder, _store
    if not INDEX_DIR.exists():
        logger.warning("Guide index is missing at %s; retrieval skipped", INDEX_DIR)
        return None
    _embedder = TfidfEmbedder.load(INDEX_DIR / "vectorizer.joblib")
    _store = NumpyStore.load(INDEX_DIR)
    return _embedder, _store


def retrieve(city: str, query: str, k: int = 4) -> list[dict[str, Any]]:
    """Return relevant guide passages for a city, or an empty list."""
    if k <= 0:
        return []
    loaded = _load_index()
    if loaded is None:
        return []
    embedder, store = loaded
    query_vector = embedder.transform([query])[0]
    matches = store.query(query_vector, k=k, city=city)
    return [
        {
            "text": match["text"],
            "section": match["section"],
            "source_name": match["source_name"],
            "source_url": match["source_url"],
            "score": match["score"],
        }
        for match in matches
        if match["score"] >= MIN_SIMILARITY
    ]


def retrieve_activity_passages(city: str, interests: list[str]) -> list[dict[str, Any]]:
    """Return See/Do chunks ranked by their best interest score, then guide order."""
    loaded = _load_index()
    if loaded is None:
        return []
    embedder, store = loaded
    eligible = [
        (index, metadata)
        for index, metadata in enumerate(store.metadata)
        if metadata.get("city") == city
        and metadata.get("section", "").casefold() in {"see", "do"}
    ]
    if not eligible:
        return []

    indexes_by_key: dict[tuple[str, str, str, str], list[int]] = {}
    for index, metadata in eligible:
        key = (
            metadata.get("text", ""), metadata.get("section", ""),
            metadata.get("source_name", ""), metadata.get("source_url", ""),
        )
        indexes_by_key.setdefault(key, []).append(index)

    scores = {index: 0.0 for index, _ in eligible}
    for interest in interests:
        vector = embedder.transform([interest])[0]
        matches = store.query(vector, k=len(store.metadata), city=city)
        for match in matches:
            key = (
                match.get("text", ""), match.get("section", ""),
                match.get("source_name", ""), match.get("source_url", ""),
            )
            for index in indexes_by_key.get(key, []):
                scores[index] = max(scores[index], float(match.get("score", 0.0)))

    return [
        {
            "text": metadata.get("text", ""),
            "section": metadata.get("section", ""),
            "source_name": metadata.get("source_name", ""),
            "source_url": metadata.get("source_url", ""),
            "score": scores[index],
        }
        for index, metadata in sorted(eligible, key=lambda pair: (-scores[pair[0]], pair[0]))
    ]


def clear_index_cache() -> None:
    """Clear the process-local lazy index cache, primarily for tests."""
    global _embedder, _store
    _embedder = None
    _store = None
