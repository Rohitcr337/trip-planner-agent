"""Build a local TF-IDF guide index."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

from backend.app.chunking import chunk_guide
from backend.app.vector_store import NumpyStore, TfidfEmbedder


ROOT = Path(__file__).resolve().parent
DEFAULT_GUIDES_DIR = ROOT / "data" / "guides"
DEFAULT_INDEX_DIR = ROOT / "index"


def ingest_guides(
    guides_dir: str | Path = DEFAULT_GUIDES_DIR,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
) -> dict[str, int]:
    """Rebuild the guide index and print totals grouped by city."""
    guide_paths = sorted(Path(guides_dir).glob("*.md"))
    chunks = [chunk for path in guide_paths for chunk in chunk_guide(path)]
    texts = [chunk.text for chunk in chunks]
    metadata = [{**chunk.metadata, "text": chunk.text} for chunk in chunks]

    target = Path(index_dir)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    embedder = TfidfEmbedder().fit(texts)
    store = NumpyStore()
    store.add(embedder.transform(texts), metadata)
    store.save(target)
    embedder.save(target / "vectorizer.joblib")

    counts = Counter(item["city"] for item in metadata)
    for city, count in sorted(counts.items()):
        print(f"Stored {count} chunks for {city}")
    return dict(counts)


if __name__ == "__main__":
    ingest_guides()
