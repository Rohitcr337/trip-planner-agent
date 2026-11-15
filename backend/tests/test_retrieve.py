from backend.app.retrieve import clear_index_cache, retrieve
from backend.app.vector_store import NumpyStore, TfidfEmbedder


def _build_index(directory):
    texts = ["Visit the old square museum.", "Walk beside the river market."]
    metadata = [
        {
            "city": "Alpha",
            "section": "Places",
            "source_name": "Made-up source",
            "source_url": "https://example.test/alpha",
            "text": texts[0],
        },
        {
            "city": "Beta",
            "section": "Places",
            "source_name": "Made-up source",
            "source_url": "https://example.test/beta",
            "text": texts[1],
        },
    ]
    embedder = TfidfEmbedder().fit(texts)
    store = NumpyStore()
    store.add(embedder.transform(texts), metadata)
    store.save(directory)
    embedder.save(directory / "vectorizer.joblib")


def test_retrieve_loads_lazily_filters_city_and_returns_metadata(tmp_path, monkeypatch):
    _build_index(tmp_path)
    import backend.app.retrieve as retrieve_module

    monkeypatch.setattr(retrieve_module, "INDEX_DIR", tmp_path)
    clear_index_cache()

    results = retrieve("Alpha", "old square", k=4)

    assert len(results) == 1
    assert results[0]["text"] == "Visit the old square museum."
    assert results[0]["section"] == "Places"
    assert results[0]["source_name"] == "Made-up source"
    assert results[0]["source_url"] == "https://example.test/alpha"


def test_retrieve_returns_empty_for_missing_index_and_irrelevant_query(tmp_path, monkeypatch):
    import backend.app.retrieve as retrieve_module

    monkeypatch.setattr(retrieve_module, "INDEX_DIR", tmp_path / "missing")
    clear_index_cache()
    assert retrieve("Alpha", "anything") == []

    _build_index(tmp_path)
    monkeypatch.setattr(retrieve_module, "INDEX_DIR", tmp_path)
    clear_index_cache()
    assert retrieve("Alpha", "zebra volcano") == []
