"""Focused safety checks for semantically interpreted field candidates.

Nemotron owns the meaning of a natural turn. These checks do not try to infer
that meaning again; they enforce high-risk constraints that are explicit in
the field schema or exposed by identity/finite-choice ambiguity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from .models import AgentFieldValue, FormAgentError, FormAgentField


@dataclass(frozen=True)
class CandidateConstraintFailure:
    reason: str
    accepted_shape: str


class CandidateConstraintViolation(FormAgentError):
    """A proposal conflicts with an explicit high-risk field constraint."""

    def __init__(self, failure: CandidateConstraintFailure) -> None:
        super().__init__(failure.reason)
        self.failure = failure


_SPELLED_LETTER_RUN = re.compile(
    r"(?<![A-Za-z])(?:[A-Za-z](?:\s*[.\-]\s*|\s+)){2,}"
    r"[A-Za-z](?:\.)?(?![A-Za-z])"
)
_NAME_HINT = re.compile(
    r"\b(?:name|surname|forename|given\s+name|family\s+name)\b",
    re.IGNORECASE,
)
_DAY_FIRST_HINT = re.compile(r"\bdd\s*[/.-]\s*mm\s*[/.-]\s*yyyy\b", re.I)
_MONTH_FIRST_HINT = re.compile(r"\bmm\s*[/.-]\s*dd\s*[/.-]\s*yyyy\b", re.I)
_MONTH_YEAR_HINT = re.compile(r"\bmm\s*[/.-]\s*yyyy\b", re.I)
_NUMERIC_DATE = re.compile(
    r"(?<!\d)(?P<first>\d{1,2})[-/.](?P<second>\d{1,2})[-/.]"
    r"(?P<year>\d{4})(?!\d)"
)
_SLASH_NUMERIC_DATE = re.compile(
    r"(?P<first>\d{1,2})/(?P<second>\d{1,2})/(?P<year>\d{4})"
)
_SLASH_MONTH_YEAR = re.compile(r"(?P<month>\d{1,2})/(?P<year>\d{4})")
_YEAR_MONTH_EVIDENCE = re.compile(r"(?<!\d)\d{4}[-/.]\d{1,2}(?!\d)")
_HOUSING_HINT = re.compile(
    r"\b(?:capacity\s+in\s+which\s+you\s+occupy|housing\s+arrangement|"
    r"occupy\s+the\s+premises|tenant|owner[- ]occupier|temporary\s+accommodation)\b",
    re.IGNORECASE,
)
_LIVING_ALONE = re.compile(
    r"\b(?:live|living|stay|staying)\s+(?:alone|by\s+myself|on\s+my\s+own)\b|"
    r"\b(?:alone|by\s+myself|on\s+my\s+own)\b",
    re.IGNORECASE,
)
_TENURE_EVIDENCE = re.compile(
    r"\b(?:tenant|tenancy|rent|renter|lease|owner|own|mortgage|"
    r"hostel|shelter|temporary\s+accommodation|no\s+fixed\s+address|homeless)\b",
    re.IGNORECASE,
)
_NAME_FRAMING_WORDS = {
    "as",
    "be",
    "called",
    "family",
    "first",
    "for",
    "full",
    "given",
    "is",
    "it",
    "legal",
    "last",
    "my",
    "name",
    "official",
    "please",
    "spell",
    "spelled",
    "spelling",
    "surname",
    "the",
    "this",
}


def validate_candidate_constraints(
    field: FormAgentField,
    value: AgentFieldValue,
    evidence: str,
) -> CandidateConstraintFailure | None:
    """Return one targeted clarification when an explicit constraint fails."""

    metadata = " ".join(
        part
        for part in (
            field.id,
            field.label,
            field.question,
            field.help_text,
            field.section,
        )
        if part
    )

    date_failure = _validate_date_constraint(metadata, value, evidence)
    if date_failure is not None:
        return date_failure

    name_failure = _validate_name_spelling_constraint(metadata, value, evidence)
    if name_failure is not None:
        return name_failure

    evidence_failure = validate_candidate_evidence_constraints(field, evidence)
    if evidence_failure is not None:
        return evidence_failure

    return None


def validate_candidate_evidence_constraints(
    field: FormAgentField,
    evidence: str,
) -> CandidateConstraintFailure | None:
    """Reject schema-relevant ambiguity without choosing a candidate value."""

    metadata = " ".join(
        part
        for part in (
            field.id,
            field.label,
            field.question,
            field.help_text,
            field.section,
        )
        if part
    )
    if (
        field.type == "dropdown"
        and _HOUSING_HINT.search(metadata)
        and _LIVING_ALONE.search(evidence)
        and _TENURE_EVIDENCE.search(evidence) is None
    ):
        return CandidateConstraintFailure(
            reason=(
                "Living alone tells me who is in the home, but it does not "
                "tell me whether you rent, own, stay with someone, or have "
                "another housing arrangement."
            ),
            accepted_shape=(
                "Tell me which available housing option describes your legal "
                "or practical arrangement."
            ),
        )

    return None


def enforce_candidate_constraints(
    field: FormAgentField,
    value: AgentFieldValue,
    evidence: str,
) -> None:
    """Raise a typed violation so every proposal path can clarify safely."""

    failure = validate_candidate_constraints(field, value, evidence)
    if failure is not None:
        raise CandidateConstraintViolation(failure)


def _validate_date_constraint(
    metadata: str,
    value: AgentFieldValue,
    evidence: str,
) -> CandidateConstraintFailure | None:
    if not isinstance(value, str):
        return None
    day_first = _DAY_FIRST_HINT.search(metadata) is not None
    month_first = _MONTH_FIRST_HINT.search(metadata) is not None
    if not day_first and not month_first:
        if _MONTH_YEAR_HINT.search(metadata) is None:
            return None
        if _YEAR_MONTH_EVIDENCE.search(evidence) is not None:
            return CandidateConstraintFailure(
                reason=(
                    "You gave the year first, but this field asks for the "
                    "month first. I do not want to swap them without checking."
                ),
                accepted_shape=(
                    "Say the month in words, or provide it in MM/YYYY format."
                ),
            )
        month_year = _SLASH_MONTH_YEAR.fullmatch(value.strip())
        if month_year is None or not 1 <= int(month_year.group("month")) <= 12:
            return CandidateConstraintFailure(
                reason="The prepared month does not match the requested MM/YYYY format.",
                accepted_shape="Provide a valid month and year in MM/YYYY format.",
            )
        return None

    expected = "DD/MM/YYYY" if day_first else "MM/DD/YYYY"
    evidence_match = _NUMERIC_DATE.search(evidence)
    if evidence_match is not None:
        first = int(evidence_match.group("first"))
        second = int(evidence_match.group("second"))
        if (day_first and second > 12) or (month_first and first > 12):
            return CandidateConstraintFailure(
                reason=(
                    f'You gave “{evidence_match.group(0)}”, but this field uses '
                    f"{expected}. I do not want to swap the day and month "
                    "without checking with you."
                ),
                accepted_shape=(
                    "Say the date with the month in words, or give it in "
                    f"{expected} format."
                ),
            )

    value_match = _SLASH_NUMERIC_DATE.fullmatch(value.strip())
    if value_match is None:
        return CandidateConstraintFailure(
            reason=f"The prepared date does not match the requested {expected} format.",
            accepted_shape=f"Provide the date in {expected} format.",
        )
    first = int(value_match.group("first"))
    second = int(value_match.group("second"))
    year = int(value_match.group("year"))
    month, day = (second, first) if day_first else (first, second)
    try:
        datetime(year, month, day)
    except ValueError:
        return CandidateConstraintFailure(
            reason="That is not a valid calendar date in the requested format.",
            accepted_shape=f"Provide a valid date in {expected} format.",
        )
    return None


def _validate_name_spelling_constraint(
    metadata: str,
    value: AgentFieldValue,
    evidence: str,
) -> CandidateConstraintFailure | None:
    if not isinstance(value, str) or _NAME_HINT.search(metadata) is None:
        return None
    spelled_runs = list(_SPELLED_LETTER_RUN.finditer(evidence))
    if not spelled_runs:
        return None

    without_runs = evidence
    joined_runs: list[str] = []
    for match in reversed(spelled_runs):
        joined = re.sub(r"[^A-Za-z]", "", match.group(0)).casefold()
        joined_runs.append(joined)
        without_runs = without_runs[: match.start()] + " " + without_runs[match.end() :]
    ordinary_words = [
        word.casefold()
        for word in re.findall(r"[A-Za-z][A-Za-z'’-]+", without_runs)
        if len(word) > 1 and word.casefold() not in _NAME_FRAMING_WORDS
    ]
    joined_runs.reverse()

    # A normal component followed by a separately spelled component is safe
    # only when the candidate preserves that exact concatenation. Repeating or
    # conflicting with the normal component is ambiguous and needs a re-ask.
    if any(
        run.startswith(word) or word.startswith(run)
        for run in joined_runs
        for word in ordinary_words
    ):
        return CandidateConstraintFailure(
            reason=(
                "I heard both a spoken name and a different or repeated "
                "letter-by-letter version."
            ),
            accepted_shape=(
                "Please say the full name once, or spell only the uncertain "
                "part once."
            ),
        )

    expected_letters = "".join((*ordinary_words, *joined_runs))
    candidate_letters = "".join(re.findall(r"[A-Za-z]", value)).casefold()
    if candidate_letters != expected_letters:
        return CandidateConstraintFailure(
            reason=(
                "The prepared name does not preserve the spoken and spelled "
                "letters in the order you supplied."
            ),
            accepted_shape=(
                "Please repeat the name, spelling only the part that may have "
                "been misheard."
            ),
        )
    return None
