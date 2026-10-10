from __future__ import annotations

from datetime import datetime
import re

from ..models import FormAgentField
from .common import preflight_message, semantic_text, strip_framing
from .models import (
    AnswerAdapterResult,
    ClarificationNeeded,
    MatchedAnswer,
)


_GENERAL_FRAMES = (
    re.compile(
        r"^(?:please\s+)?(?:enter|use|put)\s+(?P<value>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:the\s+answer|my\s+answer|it)\s+is\s+(?P<value>.+)$",
        re.IGNORECASE,
    ),
)
_NAME_FRAMES = (
    re.compile(
        r"^(?:please\s+)?use\s+(?P<value>.+?)\s+instead[.!]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:my\s+)?(?:full\s+|legal\s+|family\s+|first\s+|last\s+)?"
        r"name\s+is\s+(?P<value>.+)$",
        re.IGNORECASE,
    ),
    re.compile(r"^i\s+am\s+(?P<value>.+)$", re.IGNORECASE),
) + _GENERAL_FRAMES
_FREE_TEXT_FRAMES = (
    re.compile(
        r"^(?:please\s+)?use\s+(?P<value>.+?)\s+instead[.!]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?keep\s+(?:the\s+)?(?:label|text|answer)\s+as\s+"
        r"(?P<value>.+)$",
        re.IGNORECASE,
    ),
) + _GENERAL_FRAMES
_DATE_FRAMES = (
    re.compile(
        r"^(?:my\s+)?(?:date|date\s+of\s+birth|birth\s+date)\s+is\s+"
        r"(?P<value>.+)$",
        re.IGNORECASE,
    ),
) + _GENERAL_FRAMES
_ADDRESS_FRAMES = (
    re.compile(
        r"^(?:my\s+)?(?:home\s+|postal\s+|street\s+)?address\s+is\s+"
        r"(?P<value>.+)$",
        re.IGNORECASE,
    ),
    re.compile(r"^i\s+live\s+at\s+(?P<value>.+)$", re.IGNORECASE),
) + _GENERAL_FRAMES
_POSTCODE_FRAMES = (
    re.compile(
        r"^(?:my\s+)?(?:postcode|postal\s+code|zip\s+code)\s+is\s+"
        r"(?P<value>.+)$",
        re.IGNORECASE,
    ),
) + _GENERAL_FRAMES
_PHONE_FRAMES = (
    re.compile(
        r"^(?:my\s+)?(?:phone|telephone|mobile|contact)\s+(?:number\s+)?is\s+"
        r"(?P<value>.+)$",
        re.IGNORECASE,
    ),
) + _GENERAL_FRAMES
_UNCERTAIN_PATTERN = re.compile(
    r"\b(?:maybe|perhaps|not\s+sure|unsure|i\s+think|probably|possibly)\b",
    re.IGNORECASE,
)
_RELATIVE_DATE_PATTERN = re.compile(
    r"\b(?:today|tomorrow|yesterday|next|last)\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_PATTERN = re.compile(
    r"^(?P<first>\d{1,2})[/.](?P<second>\d{1,2})[/.](?P<year>\d{4})$"
)
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_YEAR_PATTERN = re.compile(
    r"^(?P<month>\d{1,2})[/.](?P<year>\d{4})$"
)
_POSTCODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{0,10}[A-Za-z0-9]$")
_PHONE_PATTERN = re.compile(
    r"^\+?[0-9() -]+(?:\s*(?:x|ext\.?|extension)\s*\d+)?$",
    re.IGNORECASE,
)
_STREET_CUE_PATTERN = re.compile(
    r"\b(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|"
    r"place|pl|way|close|crescent|terrace|boulevard|blvd|flat|apartment|"
    r"apt|suite|unit|po\s+box)\b",
    re.IGNORECASE,
)


def adapt_name(field: FormAgentField, message: str) -> AnswerAdapterResult:
    accepted_shape = "Provide the exact name to enter, such as Ada Lovelace."
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _UNCERTAIN_PATTERN.search(candidate):
        return ClarificationNeeded(
            reason="Your answer does not identify one definite name.",
            accepted_shape=accepted_shape,
        )
    candidate = strip_framing(candidate, _NAME_FRAMES)
    if (
        not candidate
        or candidate.casefold() in {"same", "same as above", "unknown"}
        or candidate.isnumeric()
        or len(candidate.split()) > 12
    ):
        return ClarificationNeeded(
            reason="I could not identify one exact name to enter.",
            accepted_shape=accepted_shape,
        )
    return MatchedAnswer(candidate)


def adapt_free_text(field: FormAgentField, message: str) -> AnswerAdapterResult:
    accepted_shape = "Provide the exact text you want entered."
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _UNCERTAIN_PATTERN.search(candidate):
        return ClarificationNeeded(
            reason="Your answer does not identify one definite value.",
            accepted_shape=accepted_shape,
        )
    candidate = strip_framing(candidate, _FREE_TEXT_FRAMES)
    if not candidate:
        return ClarificationNeeded(
            reason="I could not identify exact text to enter.",
            accepted_shape=accepted_shape,
        )
    return MatchedAnswer(candidate)


def adapt_date(field: FormAgentField, message: str) -> AnswerAdapterResult:
    date_format = _expected_date_format(field)
    accepted_shape = _date_answer_shape(date_format)
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _UNCERTAIN_PATTERN.search(candidate) or _RELATIVE_DATE_PATTERN.search(
        candidate
    ):
        return ClarificationNeeded(
            reason="Your answer does not provide one exact calendar date.",
            accepted_shape=accepted_shape,
        )
    candidate = strip_framing(candidate, _DATE_FRAMES)

    parsed_named = _parse_named_date(candidate)
    if date_format in {"day_first", "month_first"}:
        parsed = parsed_named or _parse_ordered_numeric_date(
            candidate,
            day_first=date_format == "day_first",
        )
        if parsed is None:
            return ClarificationNeeded(
                reason="The date does not match the format requested by this field.",
                accepted_shape=accepted_shape,
            )
        formatted = (
            parsed.strftime("%d/%m/%Y")
            if date_format == "day_first"
            else parsed.strftime("%m/%d/%Y")
        )
        return MatchedAnswer(formatted)

    if date_format == "month_year":
        match = _MONTH_YEAR_PATTERN.fullmatch(candidate)
        if match is None:
            return ClarificationNeeded(
                reason=(
                    "This field requires a month and year, not a full or "
                    "relative date."
                ),
                accepted_shape=accepted_shape,
            )
        try:
            parsed = datetime.strptime(
                f"{int(match.group('month')):02d}/{match.group('year')}",
                "%m/%Y",
            )
        except ValueError:
            return ClarificationNeeded(
                reason="That month and year are not a valid calendar value.",
                accepted_shape=accepted_shape,
            )
        return MatchedAnswer(parsed.strftime("%m/%Y"))

    if _ISO_DATE_PATTERN.fullmatch(candidate):
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
        except ValueError:
            return ClarificationNeeded(
                reason="That is not a valid calendar date.",
                accepted_shape=accepted_shape,
            )
        return MatchedAnswer(candidate)
    if parsed_named is not None:
        return MatchedAnswer(candidate)

    numeric_match = _NUMERIC_DATE_PATTERN.fullmatch(candidate)
    if numeric_match is None:
        return ClarificationNeeded(
            reason="I could not identify one complete calendar date.",
            accepted_shape=accepted_shape,
        )
    first = int(numeric_match.group("first"))
    second = int(numeric_match.group("second"))
    if first <= 12 and second <= 12:
        return ClarificationNeeded(
            reason=(
                "The numeric date is locale-sensitive, so I cannot tell which "
                "part is the month."
            ),
            accepted_shape=accepted_shape,
        )
    day_first = first > 12
    if _parse_ordered_numeric_date(candidate, day_first=day_first) is None:
        return ClarificationNeeded(
            reason="That is not a valid calendar date.",
            accepted_shape=accepted_shape,
        )
    return MatchedAnswer(candidate)


def adapt_address(field: FormAgentField, message: str) -> AnswerAdapterResult:
    accepted_shape = (
        "Provide one exact address, such as 10 Main Street, London."
    )
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    if _UNCERTAIN_PATTERN.search(candidate):
        return ClarificationNeeded(
            reason="Your answer does not identify one definite address.",
            accepted_shape=accepted_shape,
        )
    candidate = strip_framing(candidate, _ADDRESS_FRAMES)
    if " or " in candidate.casefold():
        return ClarificationNeeded(
            reason="Your answer contains more than one possible address.",
            accepted_shape=accepted_shape,
        )
    if candidate.casefold() in {"same", "same as above", "current address"}:
        return ClarificationNeeded(
            reason="That answer refers to information not supplied in this message.",
            accepted_shape=accepted_shape,
        )
    if len(candidate.split()) < 2 or not (
        any(character.isdigit() for character in candidate)
        or _STREET_CUE_PATTERN.search(candidate)
        or "," in candidate
    ):
        return ClarificationNeeded(
            reason="I could not identify a complete address to enter.",
            accepted_shape=accepted_shape,
        )
    return MatchedAnswer(candidate)


def adapt_postcode(field: FormAgentField, message: str) -> AnswerAdapterResult:
    accepted_shape = "Provide one postcode or ZIP code exactly as you use it."
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    candidate = strip_framing(candidate, _POSTCODE_FRAMES)
    if " or " in candidate.casefold():
        return ClarificationNeeded(
            reason="Your answer contains more than one possible postcode.",
            accepted_shape=accepted_shape,
        )
    if not _POSTCODE_PATTERN.fullmatch(candidate):
        return ClarificationNeeded(
            reason="I could not isolate one postcode without changing its format.",
            accepted_shape=accepted_shape,
        )
    return MatchedAnswer(candidate)


def adapt_phone(field: FormAgentField, message: str) -> AnswerAdapterResult:
    accepted_shape = (
        "Provide one phone number, including any country code or extension you use."
    )
    candidate = preflight_message(message, accepted_shape=accepted_shape)
    if not isinstance(candidate, str):
        return candidate
    candidate = strip_framing(candidate, _PHONE_FRAMES)
    if " or " in candidate.casefold():
        return ClarificationNeeded(
            reason="Your answer contains more than one possible phone number.",
            accepted_shape=accepted_shape,
        )
    digits = [character for character in candidate if character.isdigit()]
    if not _PHONE_PATTERN.fullmatch(candidate) or not 7 <= len(digits) <= 18:
        return ClarificationNeeded(
            reason="I could not isolate one complete phone number safely.",
            accepted_shape=accepted_shape,
        )
    return MatchedAnswer(candidate)


def _expected_date_format(field: FormAgentField) -> str | None:
    metadata = semantic_text(field.id, field.label, field.question)
    compact = re.sub(r"\s+", "", metadata)
    if any(marker in compact for marker in ("dd/mm/yyyy", "dd.mm.yyyy")) or (
        "day" in metadata and "month" in metadata and "year" in metadata
        and metadata.index("day") < metadata.index("month")
    ):
        return "day_first"
    if any(marker in compact for marker in ("mm/dd/yyyy", "mm.dd.yyyy")) or (
        "month" in metadata and "day" in metadata and "year" in metadata
        and metadata.index("month") < metadata.index("day")
    ):
        return "month_first"
    if "mm/yyyy" in compact or "mm/yyyy" in metadata:
        return "month_year"
    return None


def _date_answer_shape(date_format: str | None) -> str:
    if date_format == "day_first":
        return "Provide a date in DD/MM/YYYY format, such as 04/03/1990."
    if date_format == "month_first":
        return "Provide a date in MM/DD/YYYY format, such as 03/04/1990."
    if date_format == "month_year":
        return "Provide a month and year in MM/YYYY format, such as 03/2026."
    return "Use an unambiguous date, such as 4 March 1990 or 1990-03-04."


def _parse_ordered_numeric_date(
    value: str,
    *,
    day_first: bool,
) -> datetime | None:
    match = _NUMERIC_DATE_PATTERN.fullmatch(value)
    if match is None:
        return None
    first = int(match.group("first"))
    second = int(match.group("second"))
    year = int(match.group("year"))
    month, day = (second, first) if day_first else (first, second)
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_named_date(value: str) -> datetime | None:
    normalized = re.sub(r"\s+", " ", value.strip())
    for date_format in (
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
    ):
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    return None
