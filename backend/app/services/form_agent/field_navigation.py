from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Optional

from .models import FormAgentField, FieldStatus


NavigationKind = Literal[
    "select",
    "reopen",
    "correct",
    "review_value",
    "review_statuses",
    "cancel_correction",
]


@dataclass(frozen=True)
class NavigationDecision:
    kind: NavigationKind
    matches: tuple[FormAgentField, ...] = ()
    statuses: tuple[FieldStatus, ...] = ()


_CANCEL_CORRECTION_PATTERN = re.compile(
    r"^(?:(?:actually|wait)[,!]?\s+(?:(?:it|that)\s+)?"
    r"(?:was|is)\s+(?:right|correct)[,!]?\s+)?"
    r"(?:please\s+)?(?:cancel|stop|abandon|forget)"
    r"(?:\s+(?:this|that|the))?\s+(?:correction|change|replacement)"
    r"(?:\s+for\s+now)?[.!]?$|"
    r"^(?:actually[,!]?\s+)?(?:leave|keep)\s+(?:it|that|the\s+answer)\s+"
    r"unchanged\s+and\s+cancel[.!]?$",
    re.IGNORECASE,
)
_STATUS_REVIEW_PATTERN = re.compile(
    r"\b(?:list|show|summari[sz]e|tell\s+me)\b.*"
    r"\b(?:confirmed|completed|answered|skipped|unanswered|remaining|left)\b|"
    r"\b(?:which|what)\b.*\b(?:fields?|questions?)\b.*"
    r"\b(?:confirmed|completed|answered|skipped|unanswered|remaining|left)\b|"
    r"\b(?:which|what)\b.*"
    r"\b(?:confirmed|completed|answered|skipped|unanswered|remaining|left)\b"
    r".*\b(?:fields?|questions?)\b|"
    r"\b(?:did|have)\s+i\s+(?:skip|skipped)\s+anything\b|"
    r"\bis\s+anything\s+(?:still\s+)?(?:skipped|unanswered|left)\b|"
    r"\bwhat\s+have\s+we\s+(?:completed|confirmed|answered)\b",
    re.IGNORECASE,
)
_VALUE_REVIEW_PATTERNS = (
    re.compile(
        r"^(?:please\s+)?(?:what|which)\s+(?:did|have)\s+i\s+"
        r"(?:put|enter|answer|provide|confirm)(?:ed)?\s+(?:for|as)\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?what\s+(?:is|was)\s+(?:the\s+)?"
        r"(?:stored|confirmed|current)\s+(?:answer|value)\s+(?:for|of)\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?what\s+(?P<reference>.+?)\s+"
        r"(?:did\s+(?:i|we)\s+(?:put|write|enter)(?:\s+down)?|"
        r"is\s+(?:still\s+)?stored)[?!.]?$",
        re.IGNORECASE,
    ),
)
_CORRECTION_PATTERNS = (
    re.compile(
        r"^(?:i\s+(?:might|may|could)\s+|.*?[.!]\s*)?"
        r"(?:change|correct|update|replace|edit)\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:i\s+(?:want|need|would\s+like)\s+to\s+)?"
        r"(?:change|correct|update|replace|edit)\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:can|could|would)\s+(?:we|you)\s+"
        r"(?:change|correct|update|replace|edit)\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:can|could|would)\s+(?:we|you)\s+"
        r"(?:go|come|return)\s+back\s+to\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
)
_REOPEN_PATTERNS = (
    re.compile(
        r"^(?:please\s+)?(?:i\s+(?:am|'m)\s+ready\s+to\s+)?"
        r"(?:reopen|unskip)\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:let(?:'s|\s+us)\s+)?"
        r"(?:go|come|return)\s+back\s+to\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
)
_SELECT_PATTERNS = (
    re.compile(
        r"^(?:please\s+)?(?:go|move|jump|skip)\s+(?:ahead\s+)?to\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:let(?:'s|\s+us)\s+)?"
        r"(?:answer|do|open|select|work\s+on|take\s+me\s+to)\s+"
        r"(?P<reference>.+?)[?!.]?$",
        re.IGNORECASE,
    ),
)

_REFERENCE_FILLER = frozenset(
    {
        "answer",
        "field",
        "my",
        "question",
        "the",
        "value",
    }
)
_QUESTION_FILLER = frozenset(
    {
        "are",
        "can",
        "do",
        "does",
        "enter",
        "is",
        "please",
        "provide",
        "should",
        "what",
        "when",
        "where",
        "which",
        "would",
        "you",
        "your",
    }
)


def navigation_decision(
    message: str,
    fields: list[FormAgentField],
) -> Optional[NavigationDecision]:
    normalized_message = " ".join(message.strip().split())
    if _CANCEL_CORRECTION_PATTERN.fullmatch(normalized_message):
        return NavigationDecision(kind="cancel_correction")

    if _STATUS_REVIEW_PATTERN.search(normalized_message):
        statuses = _requested_statuses(normalized_message)
        if statuses:
            return NavigationDecision(
                kind="review_statuses",
                statuses=statuses,
            )

    reference = _captured_reference(normalized_message, _VALUE_REVIEW_PATTERNS)
    if reference is not None:
        return NavigationDecision(
            kind="review_value",
            matches=_match_fields(reference, fields, "confirmed"),
        )

    reference = _captured_reference(normalized_message, _CORRECTION_PATTERNS)
    if reference is not None:
        return NavigationDecision(
            kind="correct",
            matches=_match_fields(reference, fields, "confirmed"),
        )

    reference = _captured_reference(normalized_message, _REOPEN_PATTERNS)
    if reference is not None:
        return NavigationDecision(
            kind="reopen",
            matches=_match_fields(reference, fields, "skipped"),
        )

    reference = _captured_reference(normalized_message, _SELECT_PATTERNS)
    if reference is not None:
        return NavigationDecision(
            kind="select",
            matches=_match_fields(reference, fields, "unanswered"),
        )

    return None


def _captured_reference(
    message: str,
    patterns: tuple[re.Pattern[str], ...],
) -> Optional[str]:
    for pattern in patterns:
        match = pattern.fullmatch(message)
        if match is not None:
            return match.group("reference")
    return None


def _requested_statuses(message: str) -> tuple[FieldStatus, ...]:
    statuses: list[FieldStatus] = []
    if re.search(r"\b(?:confirmed|completed|answered)\b", message, re.I):
        statuses.append("confirmed")
    if re.search(r"\b(?:skip|skipped)\b", message, re.I):
        statuses.append("skipped")
    if re.search(r"\b(?:unanswered|remaining|left)\b", message, re.I):
        statuses.append("unanswered")
    return tuple(statuses)


def _match_fields(
    reference: str,
    fields: list[FormAgentField],
    required_status: FieldStatus,
) -> tuple[FormAgentField, ...]:
    candidates = [field for field in fields if field.status == required_status]
    normalized_reference = _normalize_reference(reference)
    if not normalized_reference:
        return ()

    exact_matches = [
        field
        for field in candidates
        if normalized_reference in _field_aliases(field)
    ]
    if exact_matches:
        return tuple(exact_matches)

    reference_tokens = set(normalized_reference.split())
    ranked: list[tuple[tuple[float, ...], FormAgentField]] = []
    for field in candidates:
        aliases = _field_aliases(field)
        scores = [
            _reference_match_score(reference_tokens, set(alias.split()))
            for alias in aliases
            if alias
        ]
        usable_scores = [score for score in scores if score is not None]
        if usable_scores:
            ranked.append((max(usable_scores), field))
    if not ranked:
        return ()
    best_score = max(score for score, _field in ranked)
    return tuple(field for score, field in ranked if score == best_score)


def _reference_match_score(
    reference_tokens: set[str],
    alias_tokens: set[str],
) -> tuple[float, ...] | None:
    if not reference_tokens or not alias_tokens:
        return None
    shared = reference_tokens & alias_tokens
    coverage = len(shared) / len(reference_tokens)
    if coverage < 0.5:
        return None
    non_mismatch = float("non" in alias_tokens and "non" not in reference_tokens)
    exact_reference = float(reference_tokens <= alias_tokens)
    return (
        exact_reference,
        coverage,
        float(len(shared)),
        -non_mismatch,
        -float(len(alias_tokens - reference_tokens)),
    )


def _field_aliases(field: FormAgentField) -> set[str]:
    aliases: set[str] = set()
    for value in (field.label, field.question, field.section):
        if not value:
            continue
        normalized = _normalize_text(value)
        if normalized:
            aliases.add(normalized)
        compact = " ".join(
            token
            for token in normalized.split()
            if token not in _QUESTION_FILLER
        )
        if compact:
            aliases.add(compact)
    return aliases


def _normalize_reference(value: str) -> str:
    normalized = _normalize_text(value)
    tokens = normalized.split()
    while tokens and tokens[0] in _REFERENCE_FILLER:
        tokens.pop(0)
    while tokens and tokens[-1] in _REFERENCE_FILLER:
        tokens.pop()
    return " ".join(tokens)


def _normalize_text(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    normalized: list[str] = []
    replacements = {
        "surname": ("family", "name"),
        "income": ("resources",),
    }
    for token in tokens:
        normalized.extend(replacements.get(token, (token,)))
    return " ".join(normalized)
