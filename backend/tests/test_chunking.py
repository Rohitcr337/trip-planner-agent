from backend.app.chunking import MAX_WORDS, chunk_guide


def test_chunk_guide_reads_header_and_heading_metadata(tmp_path):
    guide = tmp_path / "sample.md"
    guide.write_text(
        """---
city: Test City
source_name: Sample Source
source_url: https://example.test/guide
---

Introductory sentence.

## Food

Try the market for breakfast. Ask vendors about local dishes.

## Parks

The central park is quiet. The lake is best at sunrise.
""",
        encoding="utf-8",
    )

    chunks = chunk_guide(guide)

    assert [chunk.metadata["section"] for chunk in chunks] == ["Overview", "Food", "Parks"]
    assert all(chunk.metadata["city"] == "Test City" for chunk in chunks)
    assert all(chunk.metadata["source_name"] == "Sample Source" for chunk in chunks)
    assert all(chunk.metadata["source_url"] == "https://example.test/guide" for chunk in chunks)


def test_chunk_guide_limits_words_and_overlaps_sentences(tmp_path):
    guide = tmp_path / "sample.md"
    sentences = [f"Sentence {index} has several useful words for testing." for index in range(1, 80)]
    guide.write_text(
        "---\ncity: Test\nsource_name: Sample\nsource_url: https://example.test\n---\n"
        + "## Long section\n\n"
        + " ".join(sentences),
        encoding="utf-8",
    )

    chunks = chunk_guide(guide)

    assert len(chunks) > 1
    assert all(len(chunk.text.split()) <= MAX_WORDS for chunk in chunks)
    assert any(sentence in chunks[0].text and sentence in chunks[1].text for sentence in sentences)
