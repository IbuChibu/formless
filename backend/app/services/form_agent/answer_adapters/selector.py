from __future__ import annotations

import re
from collections.abc import Callable

from ..models import FormAgentField
from .common import semantic_text
from .models import AnswerAdapterResult, ClarificationNeeded
from .scalar import adapt_checkbox, adapt_dropdown, adapt_number
from .text import (
    adapt_address,
    adapt_date,
    adapt_free_text,
    adapt_name,
    adapt_phone,
    adapt_postcode,
)


AnswerAdapter = Callable[[FormAgentField, str], AnswerAdapterResult]

_DATE_HINT = re.compile(
    r"\b(?:date|date\s+of\s+birth|birth\s+date|dob)\b|"
    r"(?:dd|mm)[/.-](?:dd|mm|yyyy)",
    re.IGNORECASE,
)
_PHONE_HINT = re.compile(
    r"\b(?:phone|telephone|mobile|contact\s+number)\b",
    re.IGNORECASE,
)
_POSTCODE_HINT = re.compile(
    r"\b(?:postcode|postal\s+code|zip\s+code)\b",
    re.IGNORECASE,
)
_MONEY_HINT = re.compile(
    r"\b(?:amount|actual\s+cost|budget\s+(?:amount|cost)|income|receipts?|"
    r"salary|wages?|price|currency|gross\s+resources?)\b|[$£€]",
    re.IGNORECASE,
)
_NUMBER_HINT = re.compile(
    r"\b(?:count|quantity|how\s+many|number\s+of|persons?\s+ordinarily)\b",
    re.IGNORECASE,
)
_ADDRESS_HINT = re.compile(
    r"\b(?:address|street\s+number\s+and\s+name)\b",
    re.IGNORECASE,
)
_NAME_HINT = re.compile(
    r"\b(?:name|surname|forename)\b",
    re.IGNORECASE,
)


def interpret_answer(
    field: FormAgentField,
    message: str,
) -> AnswerAdapterResult:
    return select_answer_adapter(field)(field, message)


def select_answer_adapter(field: FormAgentField) -> AnswerAdapter:
    if field.type == "checkbox":
        return adapt_checkbox
    if field.type == "dropdown":
        return adapt_dropdown

    metadata = semantic_text(field.id, field.label, field.question)
    if field.type == "number":
        return _money_adapter if _MONEY_HINT.search(metadata) else _number_adapter
    if _DATE_HINT.search(metadata):
        return adapt_date
    if _PHONE_HINT.search(metadata):
        return adapt_phone
    if _POSTCODE_HINT.search(metadata):
        return adapt_postcode
    if _MONEY_HINT.search(metadata) and "edit to change item" not in metadata:
        return _money_adapter
    if _NUMBER_HINT.search(metadata):
        return _number_adapter
    if _ADDRESS_HINT.search(metadata) and "email address" not in metadata:
        return adapt_address
    if _NAME_HINT.search(metadata):
        return adapt_name
    return adapt_free_text


def clarification_for_field(field: FormAgentField) -> ClarificationNeeded:
    result = select_answer_adapter(field)(field, "")
    if not isinstance(result, ClarificationNeeded):
        raise RuntimeError("Answer adapter did not provide a clarification shape")
    return ClarificationNeeded(
        reason="I could not safely validate one value for this field.",
        accepted_shape=result.accepted_shape,
    )


def _money_adapter(
    field: FormAgentField,
    message: str,
) -> AnswerAdapterResult:
    return adapt_number(field, message, money=True)


def _number_adapter(
    field: FormAgentField,
    message: str,
) -> AnswerAdapterResult:
    return adapt_number(field, message, money=False)
