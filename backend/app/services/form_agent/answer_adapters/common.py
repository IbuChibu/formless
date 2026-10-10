from __future__ import annotations

import re

from .models import ClarificationNeeded, NotApplicable


_QUESTION_PATTERN = re.compile(
    r"(?:\?|\b(?:what|why|how|which|where|when|who|whose|explain|meaning|"
    r"mean|help|clarify)\b|^\s*(?:can|could|would|should|do|does|is|are)\b)",
    re.IGNORECASE,
)
_ADVERSARIAL_PATTERN = re.compile(
    r"\b(?:ignore|disregard|override)\b.{0,40}\b(?:instruction|prompt|rule)s?\b|"
    r"\b(?:system|developer)\s+prompt\b|\breturn\s+(?:json|an?\s+action)\b",
    re.IGNORECASE,
)
_UNKNOWN_PATTERN = re.compile(
    r"^(?:i\s+)?(?:do\s+not|don't)\s+know|^unknown$|^not\s+sure$|"
    r"^unsure$|^no\s+idea$",
    re.IGNORECASE,
)


def preflight_message(
    message: str,
    *,
    accepted_shape: str,
) -> str | ClarificationNeeded | NotApplicable:
    normalized = message.strip()
    if not normalized:
        return ClarificationNeeded(
            reason="I did not receive an answer to use.",
            accepted_shape=accepted_shape,
        )
    if _ADVERSARIAL_PATTERN.search(normalized):
        return ClarificationNeeded(
            reason=(
                "That message looks like an instruction to the assistant, not "
                "a factual value for this field."
            ),
            accepted_shape=accepted_shape,
        )
    if _QUESTION_PATTERN.search(normalized):
        return NotApplicable()
    if _UNKNOWN_PATTERN.search(normalized):
        return ClarificationNeeded(
            reason="You have not supplied a value for this field yet.",
            accepted_shape=accepted_shape,
        )
    return normalized


def strip_framing(value: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    for pattern in patterns:
        match = pattern.fullmatch(value)
        if match is not None:
            return _strip_sentence_period(match.group("value").strip())
    return value.strip()


def semantic_text(*values: str | None) -> str:
    return " ".join(value for value in values if value).casefold()


def _strip_sentence_period(value: str) -> str:
    if value.endswith(".") and not value.endswith("..."):
        return value[:-1].rstrip()
    return value
