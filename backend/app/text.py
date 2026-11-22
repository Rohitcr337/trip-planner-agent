"""Small text-cleaning helpers shared by prompt and sample-plan code."""
from __future__ import annotations

import html
import re


_EMPHASIS = re.compile(r"(?<!\w)(\*\*|__|_)(.+?)\1(?!\w)")
_LEADING_NUMBER = re.compile(r"(?m)^\s*\d+[.)]\s+")


def clean_text(value: str) -> str:
    """Decode guide markup and make its text readable as a single line."""
    text = html.unescape(str(value))
    text = _LEADING_NUMBER.sub("", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = _EMPHASIS.sub(r"\2", text)
    return re.sub(r"\s+", " ", text).strip()
