from __future__ import annotations

import re

from ..models import FormAgentField
from ..value_normalizer import canonicalize_field_value
from .common import preflight_message
from .models import (
    AnswerAdapterResult,
    ClarificationNeeded,
    MatchedAnswer,
    NotApplicable,
)


_POSITIVE_CHECKBOX_PATTERN = re.compile(
    r"^(?:yes|yeah|yep|true|checked|check(?:\s+(?:it|this|the\s+box))?|"
    r"yes,?\s+i\s+do|i\s+do|that\s+is\s+correct|that's\s+correct)[.!]?$",
    re.IGNORECASE,
)
_NEGATIVE_CHECKBOX_PATTERN = re.compile(
    r"^(?:no|nope|false|unchecked|uncheck(?:\s+(?:it|this|the\s+box))?|"
    r"leave(?:\s+(?:it|this|the\s+box))?\s+unchecked|no,?\s+i\s+do\s+not|"
    r"no,?\s+i\s+don't|i\s+do\s+not|i\s+don't|not\s+applicable|n/?a)[.!]?$",
    re.IGNORECASE,
)
_UNCERTAIN_CHOICE_PATTERN = re.compile(
    r"\b(?:maybe|perhaps|sometimes|depends|probably|possibly|not\s+sure|unsure)\b",
    re.IGNORECASE,
)
_NEGATED_OPTION_PATTERN = re.compile(
    r"\b(?:not|isn't|isnt|aren't|arent|don't|dont|doesn't|doesnt|except)\b",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(?:[$£€]\s*)?[+-]?(?:\d{1,3}(?:,\d{3})+|\d+|\.\d+)"
    r"(?:\.\d+)?(?!\w)"
)
_APPROXIMATE_NUMBER_PATTERN = re.compile(
    r"\b(?:about|approximately|approx\.?|around|roughly|nearly|almost|"
    r"more\s+than|less\s+than|at\s+least|at\s+most|between|from)\b|[~≈]",
    re.IGNORECASE,
)


def adapt_checkbox(field: FormAgentField, message: str) -> AnswerAdapterResult:
    accepted_shape = "Answer yes or no."
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _POSITIVE_CHECKBOX_PATTERN.fullmatch(candidate):
        return MatchedAnswer(True)
    if _NEGATIVE_CHECKBOX_PATTERN.fullmatch(candidate):
        return MatchedAnswer(False)
    if _UNCERTAIN_CHOICE_PATTERN.search(candidate):
        return ClarificationNeeded(
            reason="I could not tell whether the box should be checked.",
            accepted_shape=accepted_shape,
        )
    return NotApplicable()


def adapt_dropdown(field: FormAgentField, message: str) -> AnswerAdapterResult:
    options = field.options or []
    option_text = ", ".join(options[:8])
    if len(options) > 8:
        option_text += f", and {len(options) - 8} more"
    accepted_shape = f"Choose one available option: {option_text}."
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _UNCERTAIN_CHOICE_PATTERN.search(candidate):
        return ClarificationNeeded(
            reason="Your answer does not identify one definite option.",
            accepted_shape=accepted_shape,
        )
    if _NEGATED_OPTION_PATTERN.search(candidate):
        return ClarificationNeeded(
            reason="I cannot safely infer a different option from a negated choice.",
            accepted_shape=accepted_shape,
        )

    normalized_candidate = _normalize_words(candidate)
    exact_matches = [
        option
        for option in options
        if _normalize_words(option) == normalized_candidate
    ]
    if len(exact_matches) == 1:
        return MatchedAnswer(exact_matches[0])

    padded_candidate = f" {normalized_candidate} "
    mentioned_matches = [
        option
        for option in options
        if f" {_normalize_words(option)} " in padded_candidate
    ]
    if len(mentioned_matches) == 1:
        return MatchedAnswer(mentioned_matches[0])
    if len(mentioned_matches) > 1:
        return ClarificationNeeded(
            reason="Your answer could refer to more than one available option.",
            accepted_shape=accepted_shape,
        )
    if len(candidate.split()) <= 4:
        return ClarificationNeeded(
            reason="I could not match your answer to an available option.",
            accepted_shape=accepted_shape,
        )
    return NotApplicable()


def adapt_number(
    field: FormAgentField,
    message: str,
    *,
    money: bool,
) -> AnswerAdapterResult:
    accepted_shape = (
        "Provide one exact amount, such as 1250.50."
        if money
        else "Provide one exact number, such as 3 or 12.5."
    )
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _APPROXIMATE_NUMBER_PATTERN.search(candidate):
        return ClarificationNeeded(
            reason="Your answer describes an estimate or range, not one exact value.",
            accepted_shape=accepted_shape,
        )

    matches = [match.group(0) for match in _NUMBER_PATTERN.finditer(candidate)]
    if not matches:
        return NotApplicable()
    if len(matches) != 1:
        return ClarificationNeeded(
            reason="I found more than one possible numeric value in your answer.",
            accepted_shape=accepted_shape,
        )

    normalized = canonicalize_field_value("number", None, matches[0])
    if not isinstance(normalized, str) or normalized == matches[0].strip() and (
        any(character in normalized for character in "$£€,")
    ):
        return ClarificationNeeded(
            reason="I could not safely convert that value to a stored number.",
            accepted_shape=accepted_shape,
        )
    return MatchedAnswer(normalized)


def _normalize_words(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), re.UNICODE))
