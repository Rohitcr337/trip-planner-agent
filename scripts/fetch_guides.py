"""Fetch Wikivoyage travel guides via the public MediaWiki API.

Source URLs (articles fetched and saved verbatim):
  https://en.wikivoyage.org/wiki/Jaipur
  https://en.wikivoyage.org/wiki/Chennai
  https://en.wikivoyage.org/wiki/Goa

Usage:
    python scripts/fetch_guides.py
"""

import re
import sys
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = "https://en.wikivoyage.org/w/api.php"
USER_AGENT = (
    "TripPlannerAgent/1.0 (educational project; "
    "fetch_guides.py; https://en.wikivoyage.org)"
)

CITIES = [
    {"name": "Jaipur", "file": "jaipur_wikivoyage.md"},
    {"name": "Chennai", "file": "chennai_wikivoyage.md"},
    {"name": "Goa", "file": "goa_wikivoyage.md"},
]

# Navigation/meta sections to drop (drop these, keep everything else)
DROP_SECTIONS = {
    "listings", "other destinations", "cities", "regions",
    "external links", "see also", "references", "notes",
}

OUT_DIR = Path(__file__).parent.parent / "data" / "guides"


# ---------------------------------------------------------------------------
# Wikitext → Markdown helpers
# ---------------------------------------------------------------------------

def _strip_templates(text: str) -> str:
    """Remove {{...}} templates (handles nesting)."""
    result = []
    depth = 0
    i = 0
    while i < len(text):
        if text[i : i + 2] == "{{":
            depth += 1
            i += 2
        elif text[i : i + 2] == "}}":
            if depth > 0:
                depth -= 1
            i += 2
        elif depth == 0:
            result.append(text[i])
            i += 1
        else:
            i += 1
    return "".join(result)


def _strip_html_tags(text: str) -> str:
    """Remove HTML tags like <ref>, <br/>, <div>, etc."""
    # Remove ref tags with content
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    # Remove self-closing tags
    text = re.sub(r"<[^>]+/>", "", text)
    # Remove opening/closing tags
    text = re.sub(r"<[^>]+>", "", text)
    return text


def _convert_links(text: str) -> str:
    """Convert [[Article|Display]] → Display, [[Article]] → Article."""
    # [[File:...]] and [[Image:...]] — drop entirely
    text = re.sub(r"\[\[(File|Image):[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    # [[link|display text]]
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    # [[link]]
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # [url display text] — keep display text
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    # bare [url] — drop
    text = re.sub(r"\[https?://\S+\]", "", text)
    return text


def _convert_formatting(text: str) -> str:
    """Convert wikitext bold/italic to Markdown."""
    text = re.sub(r"'{5}(.+?)'{5}", r"**_\1_**", text)   # bold+italic
    text = re.sub(r"'{3}(.+?)'{3}", r"**\1**", text)       # bold
    text = re.sub(r"'{2}(.+?)'{2}", r"_\1_", text)         # italic
    return text


def _convert_lists(text: str) -> str:
    """Convert wikitext * and # list items to Markdown."""
    lines = text.splitlines()
    out = []
    for line in lines:
        m = re.match(r"^(\*+)\s*(.*)", line)
        if m:
            indent = "  " * (len(m.group(1)) - 1)
            out.append(f"{indent}- {m.group(2).strip()}")
            continue
        m = re.match(r"^(#+)\s*(.*)", line)
        if m:
            indent = "  " * (len(m.group(1)) - 1)
            out.append(f"{indent}1. {m.group(2).strip()}")
            continue
        out.append(line)
    return "\n".join(out)


def wikitext_to_markdown(wikitext: str) -> str:
    """Best-effort wikitext → Markdown conversion."""
    text = _strip_templates(wikitext)
    text = _strip_html_tags(text)
    text = _convert_links(text)
    # Convert sub-headings (=== level 3 ===, ==== level 4 ====) before bold/italic
    text = re.sub(r"^={4}\s*(.+?)\s*={4}\s*$", r"#### \1", text, flags=re.MULTILINE)
    text = re.sub(r"^={3}\s*(.+?)\s*={3}\s*$", r"### \1", text, flags=re.MULTILINE)
    text = _convert_formatting(text)
    text = _convert_lists(text)
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

def extract_sections(wikitext: str) -> list[dict]:
    """
    Split wikitext into level-2 sections, including all nested sub-section text.
    Returns list of {"level": 2, "title": str, "body": str} plus intro.
    """
    # Split only on exactly level-2 headings (== Heading ==, NOT === or ====)
    # Use negative lookahead/lookbehind to avoid matching ===
    pattern = re.compile(r"^(?!={3})==\s*(.+?)\s*==(?!=)\s*$", re.MULTILINE)
    sections = []
    matches = list(pattern.finditer(wikitext))

    # Intro text before first heading
    intro_end = matches[0].start() if matches else len(wikitext)
    intro = wikitext[:intro_end].strip()
    if intro:
        sections.append({"level": 0, "title": "__intro__", "body": intro})

    for idx, m in enumerate(matches):
        title = m.group(1).strip()
        body_start = m.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(wikitext)
        # body includes all level-3+ sub-section text
        body = wikitext[body_start:body_end].strip()
        sections.append({"level": 2, "title": title, "body": body})

    return sections


def filter_sections(sections: list[dict]) -> list[dict]:
    """Keep intro and all level-2 sections except pure navigation/meta ones."""
    kept = []
    for sec in sections:
        if sec["title"] == "__intro__":
            if sec["body"]:
                kept.append(sec)
            continue
        title_lower = sec["title"].lower()
        if title_lower in DROP_SECTIONS:
            continue
        # Drop sections that are entirely empty after template/tag stripping
        body_md = wikitext_to_markdown(sec["body"])
        if body_md.strip():
            kept.append(sec)
    return kept


def sections_to_markdown(sections: list[dict]) -> str:
    """Render filtered sections to Markdown text."""
    parts = []
    for sec in sections:
        if sec["title"] == "__intro__":
            body_md = wikitext_to_markdown(sec["body"])
            if body_md:
                parts.append(body_md)
        else:
            # Always render as ## regardless of wikitext level (all are level-2 now)
            body_md = wikitext_to_markdown(sec["body"])
            if body_md:
                parts.append(f"## {sec['title']}\n\n{body_md}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_wikitext(city: str, client: httpx.Client) -> str:
    """Fetch full wikitext for a Wikivoyage article."""
    params = {
        "action": "query",
        "titles": city,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    resp = client.get(API_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        sys.exit(f"ERROR: No pages returned for '{city}'")

    page = pages[0]
    if page.get("missing"):
        sys.exit(f"ERROR: Wikivoyage page '{city}' does not exist.")

    try:
        wikitext = page["revisions"][0]["slots"]["main"]["content"]
    except (KeyError, IndexError) as exc:
        sys.exit(f"ERROR: Could not extract wikitext for '{city}': {exc}")

    if not wikitext or len(wikitext) < 200:
        sys.exit(f"ERROR: Wikitext for '{city}' looks empty (length {len(wikitext)}).")

    return wikitext


def build_guide(city_name: str, wikitext: str) -> str:
    """Build the full guide file content (front matter + body)."""
    source_url = f"https://en.wikivoyage.org/wiki/{city_name.replace(' ', '_')}"
    front_matter = (
        f"---\n"
        f"city: {city_name}\n"
        f"source_name: Wikivoyage\n"
        f"source_url: {source_url}\n"
        f"---\n\n"
    )

    sections = extract_sections(wikitext)
    filtered = filter_sections(sections)
    body = sections_to_markdown(filtered)

    return front_matter + body


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        for city_cfg in CITIES:
            city_name = city_cfg["name"]
            out_file = OUT_DIR / city_cfg["file"]

            print(f"Fetching {city_name}...", flush=True)
            wikitext = fetch_wikitext(city_name, client)
            print(f"  Got {len(wikitext):,} wikitext chars.", flush=True)

            guide = build_guide(city_name, wikitext)
            out_file.write_text(guide, encoding="utf-8")

            word_count = len(guide.split())
            print(f"  Saved {out_file.name}  ({word_count:,} words)", flush=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
