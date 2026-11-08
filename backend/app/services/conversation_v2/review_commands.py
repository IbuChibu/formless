from __future__ import annotations

import re


_EXACT_CONFIRMATIONS = {
    "confirm",
    "confirm that",
    "confirmed",
    "correct",
    "go ahead",
    "looks good",
    "that is correct",
    "that is right",
    "that's correct",
    "that's right",
    "use that",
    "yeah",
    "yep",
    "yes",
    "yes confirm",
    "yes confirm that",
    "yes that is correct",
    "yes that is right",
    "yes that's correct",
    "yes that's right",
}


def is_explicit_confirmation(message: str) -> bool:
    """Return true only for a complete, unmistakable review confirmation."""
    normalized = re.sub(r"[^a-z0-9']+", " ", message.casefold()).strip()
    words = normalized.split()
    repeated_confirm = bool(words) and all(
        word in {"confirm", "confirmed"} for word in words
    )
    return repeated_confirm or normalized in _EXACT_CONFIRMATIONS
