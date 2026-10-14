from __future__ import annotations

from difflib import SequenceMatcher
import re

from ..models import FormAgentField
from ..value_normalizer import canonicalize_field_value
from .common import preflight_message, semantic_text
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
_NO_PEOPLE_PATTERN = re.compile(
    r"^(?:nobody|no[-\s]?one|none)(?:\s+else)?[.!]?$",
    re.IGNORECASE,
)
_COUNT_SELF_PATTERN = re.compile(
    r"\b(?:count|include)\s+(?:yourself|the\s+applicant)\b",
    re.IGNORECASE,
)
_SPOKEN_NUMBER_PATTERN = re.compile(
    r"^(?:(?:the\s+answer\s+is|it\s+is|it's|there\s+(?:is|are)|just|only)\s+)?"
    r"(?P<number>zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty)[.!]?$",
    re.IGNORECASE,
)
_SPOKEN_NUMBER_VALUES = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}


def adapt_checkbox(field: FormAgentField, message: str) -> AnswerAdapterResult:
    accepted_shape = "Answer yes or no."
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _POSITIVE_CHECKBOX_PATTERN.fullmatch(candidate):
        return MatchedAnswer(True, original_value=candidate)
    if _NEGATIVE_CHECKBOX_PATTERN.fullmatch(candidate):
        return MatchedAnswer(False, original_value=candidate)
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
        return MatchedAnswer(exact_matches[0], original_value=candidate)

    padded_candidate = f" {normalized_candidate} "
    mentioned_matches = [
        option
        for option in options
        if f" {_normalize_words(option)} " in padded_candidate
    ]
    if len(mentioned_matches) == 1:
        return MatchedAnswer(
            mentioned_matches[0],
            original_value=candidate,
        )
    if len(mentioned_matches) > 1:
        return ClarificationNeeded(
            reason="Your answer could refer to more than one available option.",
            accepted_shape=accepted_shape,
        )

    near_matches = _unique_safe_option_near_match(normalized_candidate, options)
    if near_matches is not None:
        return MatchedAnswer(near_matches, original_value=candidate)
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

    if _NO_PEOPLE_PATTERN.fullmatch(candidate):
        metadata = semantic_text(
            field.id,
            field.label,
            field.question,
            field.help_text,
        )
        if _COUNT_SELF_PATTERN.search(metadata):
            return ClarificationNeeded(
                reason=(
                    "Do you mean nobody else? This question says to count "
                    "yourself, so if it is just you the count is 1."
                ),
                accepted_shape="Tell me the exact count you want to use.",
            )
        return MatchedAnswer("0", original_value=candidate.rstrip(".!?"))

    spoken_match = _SPOKEN_NUMBER_PATTERN.fullmatch(candidate)
    if spoken_match is not None:
        spoken_number = spoken_match.group("number")
        return MatchedAnswer(
            _SPOKEN_NUMBER_VALUES[spoken_number.casefold()],
            original_value=spoken_number,
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
    return MatchedAnswer(normalized, original_value=matches[0].strip())


def _normalize_words(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), re.UNICODE))


def _unique_safe_option_near_match(
    normalized_candidate: str,
    options: list[str],
) -> str | None:
    candidate_words = normalized_candidate.split()
    if not candidate_words:
        return None

    ranked: list[tuple[float, str]] = []
    for option in options:
        normalized_option = _normalize_words(option)
        if len(normalized_option.split()) != len(candidate_words):
            continue
        ranked.append(
            (
                SequenceMatcher(
                    None,
                    normalized_candidate,
                    normalized_option,
                ).ratio(),
                option,
            )
        )
    ranked.sort(reverse=True)
    if not ranked or ranked[0][0] < 0.9:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.1:
        return None
    return ranked[0][1]
