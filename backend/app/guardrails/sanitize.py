"""Input sanitization: strip control chars, cap length, normalize whitespace,
remove HTML/script from job text before storage and prompting (04_TRD §7b)."""

import re

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

MAX_TEXT_LEN = 50_000


def sanitize_text(text: str, max_len: int = MAX_TEXT_LEN) -> str:
    text = _CONTROL_RE.sub("", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text
