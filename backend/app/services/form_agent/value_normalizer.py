from __future__ import annotations

import re
from typing import Literal, Optional, Sequence, Union


SupportedFieldType = Literal[
    "text",
    "textarea",
    "number",
    "dropdown",
    "checkbox",
]
FormFieldValue = Union[str, bool]

_NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_GROUPED_NUMBER_PATTERN = re.compile(
    r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d*)?$"
)
_NUMBER_IN_MESSAGE_PATTERN = re.compile(
    r"(?<![\w.])(?:[$£€]\s*)?[+-]?(?:\d{1,3}(?:,\d{3})+|\d+|\.\d+)"
    r"(?:\.\d+)?(?!\w)"
)
_QUESTION_CUE_PATTERN = re.compile(
    r"(?:\?|\b(?:what|why|how|which|where|when|who|whose|explain|meaning|"
    r"mean|help|clarify)\b)",
    re.IGNORECASE,
)
_NEGATION_CUE_PATTERN = re.compile(
    r"\b(?:not|never|nope|don't|doesn't|isn't|aren't|cannot|can't)\b|"
    r"\b(?:do|does|is|are|can)\s+not\b",
    re.IGNORECASE,
)
_POSITIVE_CHECKBOX_PATTERN = re.compile(
    r"^(?:yes|yeah|yep|true|checked|check(?:\s+(?:it|this|the\s+box))?|"
    r"yes,?\s+i\s+do|i\s+do|that\s+is\s+correct|that's\s+correct)[.!]?$",
    re.IGNORECASE,
)
_NEGATIVE_CHECKBOX_PATTERN = re.compile(
    r"^(?:no|nope|false|unchecked|uncheck(?:\s+(?:it|this|the\s+box))?|"
    r"leave(?:\s+(?:it|this|the\s+box))?\s+unchecked|i\s+do\s+not|"
    r"i\s+don't|not\s+applicable|n/?a)[.!]?$",
    re.IGNORECASE,
)


def validate_field_value(
    field_type: SupportedFieldType,
    options: Optional[Sequence[str]],
    value: FormFieldValue,
) -> None:
    if field_type == "checkbox":
        if not isinstance(value, bool):
            raise ValueError("Checkbox fields require boolean values")
        return

    if not isinstance(value, str):
        raise ValueError(f"{field_type} fields require string values")

    if not value.strip():
        raise ValueError("String field values cannot be empty")

    if field_type == "number" and not (
        _NUMBER_PATTERN.fullmatch(value)
        or _GROUPED_NUMBER_PATTERN.fullmatch(value)
    ):
        raise ValueError("Number fields require numeric strings")

    if field_type == "dropdown" and value not in (options or []):
        raise ValueError("Dropdown values must match an available option")


def canonicalize_field_value(
    field_type: SupportedFieldType,
    options: Optional[Sequence[str]],
    value: FormFieldValue,
) -> FormFieldValue:
    if not isinstance(value, str):
        return value

    normalized_value = value.strip()
    if field_type == "checkbox":
        checkbox_value = _checkbox_value(normalized_value)
        return checkbox_value if checkbox_value is not None else value

    if field_type == "dropdown":
        matching_option = _exact_option_match(normalized_value, options or [])
        return matching_option if matching_option is not None else value

    if field_type == "number":
        numeric_value = _normalize_number(normalized_value)
        return numeric_value if numeric_value is not None else value

    return normalized_value


def infer_unambiguous_answer(
    field_type: SupportedFieldType,
    options: Optional[Sequence[str]],
    message: str,
) -> Optional[FormFieldValue]:
    normalized_message = message.strip()
    if (
        not normalized_message
        or _looks_like_question(normalized_message)
        or _NEGATION_CUE_PATTERN.search(normalized_message)
    ):
        return None

    if field_type == "checkbox":
        return _checkbox_value(normalized_message)

    if field_type == "dropdown":
        return _option_mentioned_in_message(normalized_message, options or [])

    if field_type == "number":
        matches = [
            match.group(0)
            for match in _NUMBER_IN_MESSAGE_PATTERN.finditer(normalized_message)
        ]
        normalized_matches = {
            normalized
            for match in matches
            if (normalized := _normalize_number(match)) is not None
        }
        if len(normalized_matches) == 1:
            return normalized_matches.pop()

    return None


def _checkbox_value(value: str) -> Optional[bool]:
    normalized_value = " ".join(value.strip().split())
    if _POSITIVE_CHECKBOX_PATTERN.fullmatch(normalized_value):
        return True
    if _NEGATIVE_CHECKBOX_PATTERN.fullmatch(normalized_value):
        return False
    return None


def _exact_option_match(
    value: str,
    options: Sequence[str],
) -> Optional[str]:
    normalized_value = _normalize_words(value)
    matches = [
        option
        for option in options
        if _normalize_words(option) == normalized_value
    ]
    return matches[0] if len(matches) == 1 else None


def _option_mentioned_in_message(
    message: str,
    options: Sequence[str],
) -> Optional[str]:
    exact_match = _exact_option_match(message, options)
    if exact_match is not None:
        return exact_match

    normalized_message = f" {_normalize_words(message)} "
    matches = [
        option
        for option in options
        if f" {_normalize_words(option)} " in normalized_message
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _normalize_words(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), re.UNICODE))


def _normalize_number(value: str) -> Optional[str]:
    normalized = value.strip().replace("$", "").replace("£", "").replace("€", "")
    normalized = normalized.replace(" ", "")
    if _GROUPED_NUMBER_PATTERN.fullmatch(normalized):
        normalized = normalized.replace(",", "")
    if not _NUMBER_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _looks_like_question(message: str) -> bool:
    return _QUESTION_CUE_PATTERN.search(message) is not None
