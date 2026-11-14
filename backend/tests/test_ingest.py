import sqlite3

from ingest import ingest_guides


class FakeEmbeddingFunction:
    def embed(self, texts):
        return [[float(index), 1.0] for index, _ in enumerate(texts)]


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
    return path


def test_ingest_uses_injected_embeddings_and_is_idempotent(tmp_path, capsys):
    guides_dir = tmp_path / "guides"
    guides_dir.mkdir()
    _write_guide(guides_dir, "Alpha", "Visit the old square. Walk beside the river.")
    _write_guide(guides_dir, "Beta", "See the museum. Eat at the small market.")
    database = tmp_path / "chroma" / "guides.sqlite3"

    first_counts = ingest_guides(guides_dir, database, FakeEmbeddingFunction())
    second_counts = ingest_guides(guides_dir, database, FakeEmbeddingFunction())

    assert first_counts == {"Alpha": 1, "Beta": 1}
    assert second_counts == first_counts
    output = capsys.readouterr().out
    assert "Stored 1 chunks for Alpha" in output
    assert "Stored 1 chunks for Beta" in output
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM guide_chunks").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(DISTINCT id) FROM guide_chunks").fetchone()[0] == 2
