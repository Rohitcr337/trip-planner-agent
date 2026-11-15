import json

import numpy as np

from backend.app.vector_store import Embedder, NumpyStore, TfidfEmbedder, VectorStore
from ingest import ingest_guides


def _write_guide(directory, city, body):
    path = directory / f"{city.lower()}.md"
    path.write_text(
        f"""---
city: {city}
source_name: Made-up source
source_url: https://example.test/{city.lower()}
---

## Places

{body}
""",
        encoding="utf-8",
    )


def test_interfaces_and_numpy_store_round_trip(tmp_path):
    assert issubclass(TfidfEmbedder, Embedder)
    assert issubclass(NumpyStore, VectorStore)
    embedder = TfidfEmbedder().fit(["old square museum", "river market"])
    vectors = embedder.transform(["old square"])
    store = NumpyStore()
    store.add(
        vectors=np.vstack([vectors, embedder.transform(["river market"])]),
        metadata=[
            {"city": "Alpha", "text": "old square museum"},
            {"city": "Beta", "text": "river market"},
        ],
    )
    store.save(tmp_path)

    loaded = NumpyStore.load(tmp_path)
    results = loaded.query(vectors[0], k=2, city="Alpha")

    assert results[0]["text"] == "old square museum"
    assert loaded.metadata == store.metadata


def test_ingest_rebuilds_index_and_saves_vectorizer(tmp_path, capsys):
    guides_dir = tmp_path / "guides"
    guides_dir.mkdir()
    _write_guide(guides_dir, "Alpha", "Visit the old square. Walk beside the river.")
    _write_guide(guides_dir, "Beta", "See the city museum. Eat at the small market.")
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "stale.txt").write_text("remove me", encoding="utf-8")

    counts = ingest_guides(guides_dir, index_dir)

    assert counts == {"Alpha": 1, "Beta": 1}
    assert (index_dir / "vectors.npz").exists()
    assert (index_dir / "metadata.json").exists()
    assert (index_dir / "vectorizer.joblib").exists()
    assert not (index_dir / "stale.txt").exists()
    assert json.loads((index_dir / "metadata.json").read_text())
    assert "Stored 1 chunks for Alpha" in capsys.readouterr().out
