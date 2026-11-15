"""Interfaces and local TF-IDF vector storage for guide retrieval."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class Embedder(ABC):
    @abstractmethod
    def fit(self, texts: Sequence[str]) -> "Embedder":
        """Fit the embedder vocabulary on chunk texts."""

    @abstractmethod
    def transform(self, texts: Sequence[str]) -> np.ndarray:
        """Transform texts into numeric vectors."""


class VectorStore(ABC):
    @abstractmethod
    def add(self, vectors: np.ndarray, metadata: Sequence[dict[str, str]]) -> None:
        """Add vectors and their metadata to the store."""

    @abstractmethod
    def query(
        self, vector: Sequence[float], k: int = 4, city: str | None = None
    ) -> list[dict[str, Any]]:
        """Return the most similar records, optionally limited to a city."""

    @abstractmethod
    def save(self, directory: str | Path) -> None:
        """Persist the store."""

    @classmethod
    @abstractmethod
    def load(cls, directory: str | Path) -> "VectorStore":
        """Load a persisted store."""


class TfidfEmbedder(Embedder):
    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer()

    def fit(self, texts: Sequence[str]) -> "TfidfEmbedder":
        self.vectorizer.fit(texts)
        return self

    def transform(self, texts: Sequence[str]) -> np.ndarray:
        return self.vectorizer.transform(texts).toarray()

    def save(self, path: str | Path) -> None:
        joblib.dump(self.vectorizer, path)

    @classmethod
    def load(cls, path: str | Path) -> "TfidfEmbedder":
        embedder = cls()
        embedder.vectorizer = joblib.load(path)
        return embedder


class NumpyStore(VectorStore):
    def __init__(self) -> None:
        self.vectors = np.empty((0, 0), dtype=float)
        self.metadata: list[dict[str, str]] = []

    def add(self, vectors: np.ndarray, metadata: Sequence[dict[str, str]]) -> None:
        matrix = np.asarray(vectors, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != len(metadata):
            raise ValueError("Vectors and metadata must have matching rows")
        self.vectors = matrix.copy()
        self.metadata = [dict(item) for item in metadata]

    def query(
        self, vector: Sequence[float], k: int = 4, city: str | None = None
    ) -> list[dict[str, Any]]:
        if k <= 0 or not self.metadata:
            return []
        candidates = [
            index
            for index, item in enumerate(self.metadata)
            if city is None or item.get("city") == city
        ]
        if not candidates:
            return []
        query_vector = np.asarray(vector, dtype=float)
        norms = np.linalg.norm(self.vectors[candidates], axis=1)
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []
        scores = self.vectors[candidates].dot(query_vector) / (norms * query_norm)
        ranked = sorted(
            zip(candidates, scores), key=lambda item: float(item[1]), reverse=True
        )[:k]
        return [
            {"score": float(score), **self.metadata[index]}
            for index, score in ranked
        ]

    def save(self, directory: str | Path) -> None:
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        np.savez(target / "vectors.npz", vectors=self.vectors)
        (target / "metadata.json").write_text(
            json.dumps(self.metadata, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: str | Path) -> "NumpyStore":
        target = Path(directory)
        store = cls()
        with np.load(target / "vectors.npz") as data:
            store.vectors = data["vectors"]
        store.metadata = json.loads(
            (target / "metadata.json").read_text(encoding="utf-8")
        )
        return store
