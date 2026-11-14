"""Split guide documents into overlapping, metadata-rich chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


MAX_WORDS = 250
_HEADER_FIELDS = ("city", "source_name", "source_url")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class GuideChunk:
    text: str
    metadata: dict[str, str]


def _parse_header(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        raise ValueError("Guide must start with a YAML-style header")

    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("Guide header is not closed")

    header: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() in _HEADER_FIELDS:
            header[key.strip()] = value.strip()

    missing = [field for field in _HEADER_FIELDS if not header.get(field)]
    if missing:
        raise ValueError(f"Guide header is missing: {', '.join(missing)}")
    return header, text[end + len("\n---") :].lstrip()


def _word_count(text: str) -> int:
    return len(text.split())


def _split_long_sentence(sentence: str) -> list[str]:
    words = sentence.split()
    return [" ".join(words[start : start + MAX_WORDS]) for start in range(0, len(words), MAX_WORDS)]


def _chunk_section(section: str) -> list[str]:
    sentences = [part.strip() for part in _SENTENCE_RE.split(section.strip()) if part.strip()]
    chunks: list[str] = []
    current: list[str] = []

    for sentence in sentences:
        pieces = _split_long_sentence(sentence) if _word_count(sentence) > MAX_WORDS else [sentence]
        for piece in pieces:
            if current and _word_count(" ".join(current + [piece])) > MAX_WORDS:
                chunks.append(" ".join(current))
                current = current[-1:]
            current.append(piece)

    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_guide(path: str | Path) -> list[GuideChunk]:
    """Chunk one guide by level-two headings and return its header metadata."""
    guide_path = Path(path)
    header, body = _parse_header(guide_path.read_text(encoding="utf-8"))
    headings = list(_HEADING_RE.finditer(body))
    sections: list[tuple[str, str]] = []

    if headings and body[: headings[0].start()].strip():
        sections.append(("Overview", body[: headings[0].start()]))
    if not headings:
        sections.append(("Overview", body))
    else:
        for index, heading in enumerate(headings):
            start = heading.end()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
            sections.append((heading.group(1).strip(), body[start:end]))

    chunks: list[GuideChunk] = []
    for section, content in sections:
        metadata = {**header, "section": section}
        chunks.extend(GuideChunk(text=text, metadata=metadata) for text in _chunk_section(content))
    return chunks
