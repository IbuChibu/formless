"""Validate model-authored actions before they can enter closed state effects."""

from __future__ import annotations

import re

from .intent_policy import (
    TurnIntent,
    _comparison_words,
    classify_turn_intent,
    explanation_repair_context,
    explanations_are_near_duplicate,
)
from .models import (
    ClarifyAction,
    ConversationAction,
    ExplainAction,
    FormAgentAction,
    FormAgentError,
    FormAgentRequest,
    OfficialGuidanceCitation,
    ProposeAction,
    ReplacementProposeAction,
    request_active_field_id,
)


REPEATED_EXPLANATION_ERROR = "Form Agent repeated the previous explanation"
UNRELATED_WORKFLOW_ERROR = (
    "Form Agent added unrelated workflow commentary to an explanation"
)
LOST_ACTIVE_FIELD_ERROR = "Form Agent lost the active field context"
UNSUPPORTED_FORMAT_CLAIM_ERROR = (
    "Form Agent claimed a format that is absent from the field context"
)

_UNRELATED_WORKFLOW_PATTERN = re.compile(
    r"\b(?:first|next)\s+unanswered\s+field\b|"
    r"\bthis\s+is\s+(?:the\s+)?(?:first|next)\s+(?:field|question)\b|"
    r"\byou\s+have\s+confirmed\s+\d+\b|"
    r"\bform\s+progress\b",
    re.IGNORECASE,
)
_EXPLICIT_DATE_FORMAT_PATTERN = re.compile(
    r"\b(?:dd[/.-]mm[/.-]yyyy|mm[/.-]dd[/.-]yyyy|yyyy[/.-]mm[/.-]dd|"
    r"mm[/.-]yyyy|yyyy[/.-]mm)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_DATE_PRECISION_PATTERN = re.compile(
    r"\b(?:you\s+can|it(?:\s+is|'s)\s+okay\s+to)\s+"
    r"(?:give|enter|provide|use)\b.{0,70}\b(?:month\s+and\s+year|"
    r"month/year|best\s+estimate|approximate\s+date)\b",
    re.IGNORECASE,
)


def validate_action_for_turn(
    action: FormAgentAction,
    request: FormAgentRequest,
    guidance: tuple[OfficialGuidanceCitation, ...] = (),
    *,
    turn_intent_override: TurnIntent | None = None,
) -> None:
    intent = turn_intent_override or classify_turn_intent(request)
    if intent == "evidence_question" and not isinstance(action, ExplainAction):
        raise FormAgentError(
            "This conversational turn requires an explanation action"
        )
    if intent == "general_conversation" and not isinstance(
        action,
        ConversationAction,
    ):
        raise FormAgentError(
            "This conversational turn requires a non-mutating response"
        )
    if intent == "prose_polish" and not isinstance(
        action,
        (ProposeAction, ReplacementProposeAction, ClarifyAction),
    ):
        raise FormAgentError(
            "This prose request requires a reviewable proposal or clarification"
        )
    if intent == "wording_clarification" and not isinstance(
        action,
        (ExplainAction, ConversationAction),
    ):
        raise FormAgentError(
            "This conversational turn requires an explanation action"
        )
    if isinstance(action, ExplainAction) or (
        intent == "wording_clarification"
        and isinstance(action, ConversationAction)
    ):
        _validate_explanation_formats(action, request, guidance)
    if intent != "wording_clarification" or not isinstance(
        action,
        (ExplainAction, ConversationAction),
    ):
        return

    repair_context = explanation_repair_context(request)
    previous_explanation = repair_context.previous_explanation
    if previous_explanation is not None and explanations_are_near_duplicate(
        previous_explanation,
        action.message,
    ):
        raise FormAgentError(REPEATED_EXPLANATION_ERROR)
    if _UNRELATED_WORKFLOW_PATTERN.search(action.message) is not None:
        raise FormAgentError(UNRELATED_WORKFLOW_ERROR)
    if not _response_mentions_active_field(action.message, request):
        raise FormAgentError(LOST_ACTIVE_FIELD_ERROR)


def _validate_explanation_formats(
    action: ExplainAction | ConversationAction,
    request: FormAgentRequest,
    guidance: tuple[OfficialGuidanceCitation, ...],
) -> None:
    claimed_formats = {
        match.group(0).casefold()
        for match in _EXPLICIT_DATE_FORMAT_PATTERN.finditer(action.message)
    }
    claims_partial_or_estimated_date = (
        _UNSUPPORTED_DATE_PRECISION_PATTERN.search(action.message) is not None
    )
    if not claimed_formats and not claims_partial_or_estimated_date:
        return

    active_field_id = request_active_field_id(request)
    field = next(
        (
            candidate
            for candidate in request.fields
            if candidate.id == active_field_id
        ),
        None,
    )
    if field is None:
        raise FormAgentError(UNSUPPORTED_FORMAT_CLAIM_ERROR)
    allowed_context = " ".join(
        value
        for value in (
            field.id,
            field.label,
            field.question,
            field.help_text,
            *(field.options or []),
            *(citation.excerpt for citation in guidance),
        )
        if value
    ).casefold()
    has_unsupported_format = any(
        format_value not in allowed_context for format_value in claimed_formats
    )
    precision_is_supported = any(
        phrase in allowed_context
        for phrase in (
            "month and year",
            "month/year",
            "best estimate",
            "approximate date",
        )
    )
    if has_unsupported_format or (
        claims_partial_or_estimated_date and not precision_is_supported
    ):
        raise FormAgentError(UNSUPPORTED_FORMAT_CLAIM_ERROR)


def _response_mentions_active_field(
    message: str,
    request: FormAgentRequest,
) -> bool:
    active_field_id = request_active_field_id(request)
    field = next(
        (field for field in request.fields if field.id == active_field_id),
        None,
    )
    if field is None:
        return True

    metadata = " ".join(
        value
        for value in (
            field.label,
            field.question,
            field.help_text,
            " ".join(field.options or []),
        )
        if value
    ).casefold()
    anchors = {
        word
        for word in _comparison_words(metadata)
        if len(word) >= 4
        and word
        not in {
            "best",
            "does",
            "field",
            "form",
            "option",
            "question",
            "should",
            "this",
            "what",
            "which",
            "where",
            "would",
            "your",
        }
    }
    if re.search(r"\b(?:address|home|housing|live|living|residen)", metadata):
        anchors.update(
            {
                "address",
                "home",
                "housing",
                "live",
                "living",
                "move",
                "own",
                "rent",
                "stay",
            }
        )
    if re.search(r"\b(?:date|day|month|year|when)\b", metadata):
        anchors.update({"date", "day", "month", "year", "when"})
    if re.search(r"\b(?:income|earn|money|salary|wage)\b", metadata):
        anchors.update({"earn", "income", "money", "month", "monthly", "pay"})
    response_words = set(_comparison_words(message))
    return bool(anchors & response_words)
