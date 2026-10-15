from __future__ import annotations

from collections.abc import Callable
import re

from ..models import FormAgentField, RememberedCandidate
from .common import semantic_text
from .models import AnswerAdapterResult, MatchedAnswer


MAX_VOLUNTEERED_SCAN_FIELDS = 40

_DATE_VALUE = r"[^,;]+?"
_PRIOR_REFERENCE_PATTERN = re.compile(
    r"\b(?:already|earlier|before|previously|also|too|at\s+the\s+start|"
    r"with\s+my\s+name)\b|"
    r"\b(?:gave|provided|said|shared|told)\b.{0,80}\b(?:that|it|you)\b",
    re.IGNORECASE,
)
_BIRTH_DATE_PATTERNS = (
    re.compile(
        rf"\bi\s+was\s+born(?:\s+on)?\s+(?P<value>{_DATE_VALUE})"
        r"(?=,\s*(?:and\s+)?|;|$)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:my\s+)?(?:date\s+of\s+birth|birth\s+date)\s+is\s+"
        rf"(?P<value>{_DATE_VALUE})(?=,\s*(?:and\s+)?|;|$)",
        re.IGNORECASE,
    ),
)
_PREFERRED_NAME_PATTERNS = (
    re.compile(
        r"\b(?:please\s+)?call\s+me\s+(?P<value>[^,;]+?)"
        r"(?=,\s*(?:and\s+)?|;|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:my\s+)?preferred\s+name\s+is\s+(?P<value>[^,;]+?)"
        r"(?=,\s*(?:and\s+)?|;|$)",
        re.IGNORECASE,
    ),
)


def references_prior_answer(message: str) -> bool:
    return _PRIOR_REFERENCE_PATTERN.search(message) is not None


def merge_volunteered_candidates(
    existing: list[RememberedCandidate],
    fields: list[FormAgentField],
    active_field_id: str | None,
    message: str,
    interpreter: Callable[[FormAgentField, str], AnswerAdapterResult],
    *,
    max_candidates: int,
) -> list[RememberedCandidate]:
    """Retain only explicit, field-specific, adapter-valid later answers."""
    by_field = {candidate.field_id: candidate for candidate in existing}
    scanned = 0
    for field in fields:
        if scanned >= MAX_VOLUNTEERED_SCAN_FIELDS:
            break
        if field.id == active_field_id or field.status != "unanswered":
            continue
        scanned += 1
        candidate = _candidate_for_field(field, message, interpreter)
        if candidate is not None:
            by_field[field.id] = candidate

    ordered: list[RememberedCandidate] = []
    for field in fields:
        candidate = by_field.get(field.id)
        if candidate is not None and field.status == "unanswered":
            ordered.append(candidate)
        if len(ordered) >= max_candidates:
            break
    return ordered


def remembered_answer(
    field: FormAgentField,
    message: str,
    candidates: list[RememberedCandidate],
) -> MatchedAnswer | None:
    if not references_prior_answer(message):
        return None
    candidate = next(
        (item for item in candidates if item.field_id == field.id),
        None,
    )
    if candidate is None:
        return None
    return MatchedAnswer(
        value=candidate.value,
        original_value=candidate.original_value,
    )


def _candidate_for_field(
    field: FormAgentField,
    message: str,
    interpreter: Callable[[FormAgentField, str], AnswerAdapterResult],
) -> RememberedCandidate | None:
    metadata = semantic_text(
        field.id,
        field.label,
        field.question,
        field.help_text,
    )
    raw_candidates: list[str] = []

    if re.search(r"\b(?:date\s+of\s+birth|birth\s+date|dob)\b", metadata):
        raw_candidates.extend(_pattern_values(_BIRTH_DATE_PATTERNS, message))

    if re.search(r"\bpreferred\b.*\bname\b|\bname\b.*\bpreferred\b", metadata):
        raw_candidates.extend(_pattern_values(_PREFERRED_NAME_PATTERNS, message))

    if field.type == "dropdown":
        mentioned = [
            option
            for option in (field.options or [])
            if _contains_option(message, option)
        ]
        if len(mentioned) == 1:
            raw_candidates.append(mentioned[0])

    matched: dict[str, MatchedAnswer] = {}
    for raw_candidate in raw_candidates:
        cleaned = raw_candidate.strip().rstrip(".!?").strip()
        if not cleaned:
            continue
        result = interpreter(field, cleaned)
        if isinstance(result, MatchedAnswer):
            matched[repr(result.value)] = MatchedAnswer(
                value=result.value,
                original_value=cleaned,
            )

    if len(matched) != 1:
        return None
    answer = next(iter(matched.values()))
    return RememberedCandidate(
        field_id=field.id,
        original_value=answer.original_value,
        value=answer.value,
    )


def _pattern_values(
    patterns: tuple[re.Pattern[str], ...],
    message: str,
) -> list[str]:
    values: list[str] = []
    for pattern in patterns:
        values.extend(
            match.group("value")
            for match in pattern.finditer(message)
        )
    return values


def _contains_option(message: str, option: str) -> bool:
    normalized_message = _normalize_words(message)
    normalized_option = _normalize_words(option)
    return bool(
        normalized_option
        and re.search(
            rf"(?:^|\s){re.escape(normalized_option)}(?:$|\s)",
            normalized_message,
        )
    )


def _normalize_words(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), re.UNICODE))
