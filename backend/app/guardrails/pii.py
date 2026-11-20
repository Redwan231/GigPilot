"""PII scrubbing for uploaded samples before embedding/storage (04_TRD §7b).

Redacts obvious emails and phone numbers. This is a lightweight heuristic,
not a full PII scanner — sufficient for MVP."""

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
)


def redact_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    return text
