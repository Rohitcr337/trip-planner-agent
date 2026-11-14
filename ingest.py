"""Ingest travel guides into a small local SQLite vector store.

This is the dependency-free fallback for environments where Chroma and
PyTorch cannot be installed. Embeddings use deterministic feature hashing so
the database remains local and re-runnable.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Protocol, Sequence

from backend.app.chunking import GuideChunk, chunk_guide


ROOT = Path(__file__).resolve().parent
DEFAULT_GUIDES_DIR = ROOT / "data" / "guides"
DEFAULT_DB_PATH = ROOT / "chroma" / "guides.sqlite3"


class EmbeddingFunction(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector for each input text."""


class HashEmbeddingFunction:
    """Create compact, deterministic normalized bag-of-words vectors."""

    dimensions = 128
    _token_re = re.compile(r"[a-z0-9]+", re.IGNORECASE)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in self._token_re.findall(text.lower()):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[index] += 1.0
            magnitude = sum(value * value for value in vector) ** 0.5
            vectors.append(
                [value / magnitude for value in vector] if magnitude else vector
            )
        return vectors


def _chunk_id(chunk: GuideChunk, index: int) -> str:
    identity = "\x1f".join(
        (
            chunk.metadata["city"],
            chunk.metadata["source_url"],
            chunk.metadata["section"],
            str(index),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS guide_chunks (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            embedding TEXT NOT NULL,
            city TEXT NOT NULL,
            section TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL
        )
        """
    )


def ingest_guides(
    guides_dir: str | Path = DEFAULT_GUIDES_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    embedding_function: EmbeddingFunction | None = None,
) -> dict[str, int]:
    """Upsert all Markdown guide chunks and print totals grouped by city."""
    guide_paths = sorted(Path(guides_dir).glob("*.md"))
    embedder = embedding_function or HashEmbeddingFunction()
    chunks_by_path = [(path, chunk_guide(path)) for path in guide_paths]
    records = [
        (chunk, index)
        for _, chunks in chunks_by_path
        for index, chunk in enumerate(chunks)
    ]
    embeddings = embedder.embed([chunk.text for chunk, _ in records])
    if len(embeddings) != len(records):
        raise ValueError("Embedding function returned the wrong number of vectors")

    database = Path(db_path)
    database.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    with sqlite3.connect(database) as connection:
        _create_schema(connection)
        for ((chunk, index), embedding) in zip(records, embeddings):
            connection.execute(
                """
                INSERT INTO guide_chunks
                    (id, text, embedding, city, section, source_name, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    text = excluded.text,
                    embedding = excluded.embedding,
                    city = excluded.city,
                    section = excluded.section,
                    source_name = excluded.source_name,
                    source_url = excluded.source_url
                """,
                (
                    _chunk_id(chunk, index),
                    chunk.text,
                    json.dumps(embedding),
                    chunk.metadata["city"],
                    chunk.metadata["section"],
                    chunk.metadata["source_name"],
                    chunk.metadata["source_url"],
                ),
            )
            counts[chunk.metadata["city"]] += 1
        connection.commit()

    for city, count in sorted(counts.items()):
        print(f"Stored {count} chunks for {city}")
    return dict(counts)


if __name__ == "__main__":
    ingest_guides()
