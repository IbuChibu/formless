"""Pure deterministic grounding for bounded turn interpretations."""

from __future__ import annotations

import re
from typing import Optional

from .models import (
    AgentFieldValue,
    AssistanceNeed,
    FormAgentField,
    InteractionModePreference,
)


def evidence_is_grounded(evidence: str, message: str) -> bool:
    normalized_evidence = " ".join(evidence.casefold().split())
    normalized_message = " ".join(message.casefold().split())
    return normalized_evidence in normalized_message


def field_reference_is_grounded(field: FormAgentField, message: str) -> bool:
    field_tokens = meaning_tokens(
        " ".join(value for value in (field.id, field.label, field.question) if value)
    )
    return bool(field_tokens & meaning_tokens(message))


def candidate_is_grounded(
    field: FormAgentField,
    value: AgentFieldValue,
    evidence: str,
) -> bool:
    if isinstance(value, bool):
        normalized_evidence = evidence.casefold()
        negative = re.search(
            r"\b(?:no|not|never|none|don't|doesn't|isn't|do\s+not|does\s+not)\b",
            normalized_evidence,
        )
        if negative is not None:
            return value is False
        positive = re.search(
            r"\b(?:yes|yeah|yep|agree|accept|applies|share|i\s+do|i\s+am)\b",
            normalized_evidence,
        )
        return value is True and positive is not None

    if field.type == "dropdown":
        return value in (field.options or []) and not has_uncertainty(evidence)

    value_tokens = meaning_tokens(value)
    return bool(value_tokens) and value_tokens.issubset(meaning_tokens(evidence))


def grounded_assistance_preferences(
    needs: list[AssistanceNeed],
    interaction_mode: Optional[InteractionModePreference],
    message: str,
) -> tuple[list[AssistanceNeed], Optional[InteractionModePreference]]:
    grounded_needs: list[AssistanceNeed] = [
        need
        for need in needs
        if _ASSISTANCE_GROUNDING_PATTERNS[need].search(message) is not None
    ]
    grounded_mode: Optional[InteractionModePreference] = None
    if interaction_mode == "voice" and re.search(
        r"\b(?:prefer|rather|want|like)\b.{0,24}\b(?:speak|talk|voice)\b|"
        r"\buse\s+voice\b",
        message,
        re.IGNORECASE,
    ):
        grounded_mode = "voice"
    elif interaction_mode == "typing" and re.search(
        r"\b(?:prefer|rather|want|like)\b.{0,24}\b(?:type|typing|text)\b|"
        r"\buse\s+typing\b",
        message,
        re.IGNORECASE,
    ):
        grounded_mode = "typing"
    return grounded_needs, grounded_mode


def proposal_needs_interpretation(
    field: FormAgentField,
    message: str,
    proposed_value: AgentFieldValue,
) -> bool:
    if field.type == "textarea":
        return _CONVERSATIONAL_FRAME_PATTERN.search(message) is not None
    metadata = " ".join(
        value for value in (field.id, field.label, field.question) if value
    )
    if re.search(r"\b(?:name|surname|forename|date|address)\b", metadata, re.I):
        if len(message.split()) > 4 and proposed_value == message.rstrip(".!?"):
            return True
        if re.search(
            r"\b(?:and\s+(?:yes|no)|also|accept|born|address|live|rent|employed)\b",
            str(proposed_value),
            re.IGNORECASE,
        ):
            return True
        if re.search(
            r"\b(?:and|also)\b.{0,80}\b(?:19|20)\d{2}\b",
            message,
            re.IGNORECASE,
        ):
            return True
    return _CONVERSATIONAL_FRAME_PATTERN.search(message) is not None


def has_uncertainty(value: str) -> bool:
    return re.search(
        r"\b(?:maybe|perhaps|probably|possibly|sometimes|depends|"
        r"not\s+sure|unsure|i\s+think|or)\b",
        value,
        re.IGNORECASE,
    ) is not None


def has_explicit_negation(value: str) -> bool:
    return re.search(
        r"\b(?:no|not|never|none|don't|doesn't|isn't|do\s+not|does\s+not)\b",
        value,
        re.IGNORECASE,
    ) is not None


def looks_like_conversational_skip(message: str) -> bool:
    return re.search(
        r"\b(?:leave|skip|pass|move\s+on|circle\s+back|come\s+back)\b",
        message,
        re.IGNORECASE,
    ) is not None


def looks_like_conversational_navigation(message: str) -> bool:
    return re.search(
        r"\b(?:go\s+back|come\s+back|return\s+to|revisit|earlier|"
        r"left\s+(?:for\s+)?later)\b",
        message,
        re.IGNORECASE,
    ) is not None


def looks_like_prior_answer_reference(message: str) -> bool:
    return re.search(
        r"\b(?:already|earlier|before)\b.{0,40}\b"
        r"(?:gave|give|told|tell|provided|answered|said)\b|"
        r"\b(?:gave|told|provided|answered|said)\b.{0,40}\b"
        r"(?:already|earlier|before)\b",
        message,
        re.IGNORECASE,
    ) is not None


def must_remain_deterministic_setup_turn(message: str) -> bool:
    return re.search(
        r"\b(?:ignore\s+(?:the\s+)?system|bypass\s+(?:review|confirmation)|"
        r"confirm\s+(?:everything|every\s+answer)\s+automatically)\b|"
        r"^\s*i\s+have\s+[\w -]+[.!]?\s*$",
        message,
        re.IGNORECASE,
    ) is not None


_ASSISTANCE_GROUNDING_PATTERNS = {
    "plain_language": re.compile(
        r"\b(?:plain|simple|simpler|wording|words?|language|english|"
        r"understand|read|confus\w*|difficult)\b",
        re.IGNORECASE,
    ),
    "slower_pace": re.compile(
        r"\b(?:slow\w*|pace|rush|step\s+by\s+step|one\s+at\s+a\s+time|"
        r"overwhelm\w*|panic\w*|gently|calm)\b",
        re.IGNORECASE,
    ),
    "organise_details": re.compile(
        r"\b(?:organi[sz]\w*|sort\w*|keep\s+track|lose\s+track|"
        r"details?|information|right\s+(?:box|place))\b",
        re.IGNORECASE,
    ),
    "reassurance": re.compile(
        r"\b(?:reassur\w*|worried|nervous|stress\w*|anxious|panic\w*|"
        r"calm|mistakes?|confidence)\b",
        re.IGNORECASE,
    ),
    "explain_bureaucracy": re.compile(
        r"\b(?:official|formal|legal|government|bureaucr\w*|jargon)\b",
        re.IGNORECASE,
    ),
}


_WORD_VALUES = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16",
    "seventeen": "17", "eighteen": "18", "nineteen": "19",
    "twenty": "20", "first": "1", "second": "2", "third": "3",
    "fourth": "4", "fifth": "5", "sixth": "6", "seventh": "7",
    "eighth": "8", "ninth": "9", "tenth": "10", "eleventh": "11",
    "twelfth": "12", "thirteenth": "13", "fourteenth": "14",
    "fifteenth": "15", "sixteenth": "16", "seventeenth": "17",
    "eighteenth": "18", "nineteenth": "19", "twentieth": "20",
    "twenty-first": "21", "twenty-second": "22", "twenty-third": "23",
    "twenty-fourth": "24", "twenty-fifth": "25", "twenty-sixth": "26",
    "twenty-seventh": "27", "twenty-eighth": "28", "twenty-ninth": "29",
    "thirtieth": "30", "thirty-first": "31", "january": "1",
    "jan": "1", "february": "2", "feb": "2", "march": "3",
    "mar": "3", "april": "4", "apr": "4", "may": "5", "june": "6",
    "jun": "6", "july": "7", "jul": "7", "august": "8", "aug": "8",
    "september": "9", "sep": "9", "sept": "9", "october": "10",
    "oct": "10", "november": "11", "nov": "11", "december": "12",
    "dec": "12",
}
_MEANING_STOP_WORDS = {
    "a", "an", "and", "be", "down", "for", "is", "it", "me", "my",
    "of", "on", "put", "that", "the", "there", "this", "to", "want",
    "would", "you", "your", "thanks", "was", "can",
}


def meaning_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[\w]+(?:-[\w]+)?", value.casefold(), re.UNICODE):
        normalized = _WORD_VALUES.get(token, token)
        if normalized not in _MEANING_STOP_WORDS:
            tokens.add(normalized)
    return tokens


_CONVERSATIONAL_FRAME_PATTERN = re.compile(
    r"\b(?:you\s+can\s+put|put\s+.+\s+down|that\s+would\s+be|"
    r"you(?:'ll|\s+will)\s+want|what\s+you\s+want|actually|"
    r"for\s+that|for\s+the\s+form)\b",
    re.IGNORECASE,
)
