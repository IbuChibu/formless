from __future__ import annotations

from dataclasses import dataclass
import re

from .answer_adapters.common import semantic_text
from .models import (
    AgentFieldValue,
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    ProposeAction,
    request_message,
)
from .value_normalizer import validate_field_value


@dataclass(frozen=True)
class PreparedAnswer:
    original_value: AgentFieldValue
    prepared_value: AgentFieldValue
    transformation: str | None = None


_NAME_HINT = re.compile(
    r"\b(?:name|surname|forename|given\s+name|family\s+name)\b",
    re.IGNORECASE,
)
_DATE_HINT = re.compile(
    r"\b(?:date|date\s+of\s+birth|birth\s+date|dob)\b|"
    r"(?:dd|mm)[/.-](?:dd|mm|yyyy)",
    re.IGNORECASE,
)
_ADDRESS_HINT = re.compile(
    r"\b(?:address|street|postcode|postal\s+code|zip\s+code|phone|"
    r"telephone|mobile|email|passport|account|reference|identifier|id)\b",
    re.IGNORECASE,
)
_NAME_PARTICLES = frozenset(
    {
        "al",
        "bin",
        "da",
        "de",
        "del",
        "der",
        "di",
        "du",
        "la",
        "le",
        "van",
        "von",
    }
)


def prepare_proposal_action(
    action: ProposeAction,
    request: FormAgentRequest,
) -> ProposeAction:
    field = next(
        (field for field in request.fields if field.id == action.field_id),
        None,
    )
    if field is None:
        return action

    original_value = action.original_value
    if original_value is None:
        message = request_message(request).strip()
        original_value = message or action.value

    prepared = prepare_answer(field, original_value, action.value)
    try:
        validate_field_value(
            field.type,
            field.options,
            prepared.prepared_value,
        )
    except ValueError as error:
        raise FormAgentError(
            "Form Agent returned an invalid proposal value"
        ) from error

    return action.model_copy(
        update={
            "value": prepared.prepared_value,
            "original_value": prepared.original_value,
            "transformation": prepared.transformation,
        }
    )


def prepare_answer(
    field: FormAgentField,
    original_value: AgentFieldValue,
    interpreted_value: AgentFieldValue,
) -> PreparedAnswer:
    if isinstance(interpreted_value, bool):
        transformation = (
            "Converted your yes/no answer to the checkbox state."
            if original_value != interpreted_value
            else None
        )
        return PreparedAnswer(
            original_value=original_value,
            prepared_value=interpreted_value,
            transformation=transformation,
        )

    prepared_value = _normalize_whitespace(interpreted_value)
    metadata = semantic_text(field.id, field.label, field.question)
    transformation: str | None = None

    if _NAME_HINT.search(metadata):
        capitalized = _suggest_name_capitalization(prepared_value)
        if capitalized != prepared_value:
            prepared_value = capitalized
            transformation = (
                "Capitalization suggested; spelling and letter order preserved."
            )
    elif field.type == "textarea" and not _ADDRESS_HINT.search(metadata):
        polished = _polish_prose_presentation(prepared_value)
        if polished != prepared_value:
            prepared_value = polished
            transformation = (
                "Capitalization and punctuation suggested; wording preserved."
            )

    if transformation is None and original_value != prepared_value:
        if _DATE_HINT.search(metadata):
            transformation = "Formatted to match the date format requested."
        elif field.type == "number":
            transformation = "Removed presentation characters from the number."
        elif field.type == "dropdown":
            transformation = "Matched your answer to an available option."
        else:
            transformation = "Normalized spacing for the form."

    return PreparedAnswer(
        original_value=original_value,
        prepared_value=prepared_value,
        transformation=transformation,
    )


def preparation_is_safe(
    field: FormAgentField,
    original_value: AgentFieldValue,
    prepared_value: AgentFieldValue,
) -> bool:
    if original_value == prepared_value:
        return True

    from .answer_adapters import MatchedAnswer, interpret_answer

    adapter_input = (
        "yes"
        if original_value is True
        else "no"
        if original_value is False
        else original_value
    )
    adapter_result = interpret_answer(field, adapter_input)
    if (
        isinstance(adapter_result, MatchedAnswer)
        and adapter_result.value == prepared_value
    ):
        return True

    if isinstance(original_value, str) and isinstance(prepared_value, str):
        return _meaning_tokens(original_value) == _meaning_tokens(prepared_value)
    return False


def _normalize_whitespace(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _suggest_name_capitalization(value: str) -> str:
    letters = [character for character in value if character.isalpha()]
    if not letters or not all(character.islower() for character in letters):
        return value

    words = value.split(" ")
    prepared_words: list[str] = []
    for index, word in enumerate(words):
        if index > 0 and word.casefold() in _NAME_PARTICLES:
            prepared_words.append(word.casefold())
            continue
        prepared_words.append(_capitalize_name_word(word))
    return " ".join(prepared_words)


def _capitalize_name_word(value: str) -> str:
    pieces = re.split(r"([-’'])", value)
    return "".join(
        piece[:1].upper() + piece[1:]
        if piece and piece not in {"-", "'", "’"}
        else piece
        for piece in pieces
    )


def _polish_prose_presentation(value: str) -> str:
    if not value:
        return value
    polished = re.sub(r"\bi\b", "I", value)
    for index, character in enumerate(polished):
        if character.isalpha():
            polished = (
                polished[:index]
                + character.upper()
                + polished[index + 1 :]
            )
            break
    if polished and polished[-1] not in ".!?":
        polished += "."
    return polished


def _meaning_tokens(value: str) -> list[str]:
    return re.findall(r"[\w]+", value.casefold(), re.UNICODE)
