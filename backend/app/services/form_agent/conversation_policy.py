from __future__ import annotations

import re
from typing import Optional

from .models import (
    ClarifyAction,
    ExplainAction,
    FormAgentAction,
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    NextAction,
    ProposeAction,
    SkipAction,
    field_question,
    truncate_text,
)
from .value_normalizer import infer_unambiguous_answer


_SKIP_REQUEST_PATTERNS = (
    re.compile(
        r"^(?:please\s+)?(?:skip|pass)(?:\s+(?:this|it|this\s+field|"
        r"this\s+question))?(?:\s+for\s+(?:now|later))?[.!]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:(?:please|let's)\s+)?(?:move\s+on|"
        r"next(?:\s+(?:field|question))?)[.!]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:i(?:'d|\s+would)\s+rather\s+not\s+answer|"
        r"i\s+do\s+not\s+want\s+to\s+answer|i\s+don't\s+want\s+to\s+answer)"
        r"(?:\s+this)?(?:\s+(?:right\s+now|for\s+now))?[.!]?$",
        re.IGNORECASE,
    ),
)
_PURPOSE_QUESTION_PATTERNS = (
    re.compile(r"^why\??$", re.IGNORECASE),
    re.compile(
        r"\bwhy\b.{0,80}\b(?:ask|need(?:ed)?|require(?:d)?|request(?:ed)?|"
        r"collect(?:ed)?|want|information)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat\b.{0,60}\b(?:used for|use this for)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:purpose|reason)\b.{0,60}\b(?:field|question|information|"
        r"request)\b",
        re.IGNORECASE,
    ),
)


def unsupported_purpose_action(
    request: FormAgentRequest,
) -> Optional[ExplainAction]:
    if request.active_field_id is None:
        return None
    if not _asks_for_unsupported_purpose(request.message):
        return None

    return ExplainAction(
        action="explain",
        message=(
            "The available form context explains what to provide, but it "
            "does not provide an authoritative reason why the organisation "
            "requests it. Check the form's official instructions or ask "
            "the organisation for that reason."
        ),
        field_id=request.active_field_id,
    )


def deterministic_action(
    request: FormAgentRequest,
) -> Optional[FormAgentAction]:
    fields_by_id = {field.id: field for field in request.fields}
    active_field = (
        fields_by_id.get(request.active_field_id)
        if request.active_field_id is not None
        else None
    )

    if active_field is None:
        next_field = next(
            (
                field
                for field in request.fields
                if field.status == "unanswered"
            ),
            None,
        )
        if next_field is None:
            return NextAction(
                action="next",
                message="All supported fields have been reviewed.",
                field_id=None,
            )
        return NextAction(
            action="next",
            message=build_next_field_question(next_field),
            field_id=next_field.id,
        )

    if active_field.status != "unanswered":
        return None

    if _asks_to_skip(request.message):
        return SkipAction(
            action="skip",
            message=_build_skip_message(active_field),
            field_id=active_field.id,
        )

    inferred_value = infer_unambiguous_answer(
        active_field.type,
        active_field.options,
        request.message,
    )
    if inferred_value is None:
        return None

    return normalize_action_message(
        ProposeAction(
            action="propose",
            message="Proposal awaiting confirmation.",
            field_id=active_field.id,
            value=inferred_value,
        ),
        request,
    )


def invalid_value_clarification(
    error: FormAgentError,
    request: FormAgentRequest,
) -> Optional[ClarifyAction]:
    if str(error) != "Form Agent returned an invalid proposal value":
        return None
    if request.active_field_id is None:
        return None

    field = next(
        (
            field
            for field in request.fields
            if field.id == request.active_field_id
        ),
        None,
    )
    if field is None:
        return None

    return _build_field_clarification(field)


def unexpected_navigation_clarification(
    action: FormAgentAction,
    request: FormAgentRequest,
) -> Optional[ClarifyAction]:
    if not isinstance(action, (NextAction, SkipAction)):
        return None
    if request.active_field_id is None:
        return None

    field = next(
        (
            field
            for field in request.fields
            if field.id == request.active_field_id
        ),
        None,
    )
    if field is None or field.status != "unanswered":
        return None

    return _build_field_clarification(field)


def normalize_action_message(
    action: FormAgentAction,
    request: FormAgentRequest,
) -> FormAgentAction:
    if isinstance(action, NextAction):
        if action.field_id is None:
            return action.model_copy(
                update={"message": "All supported fields have been reviewed."}
            )

        field = next(
            field for field in request.fields if field.id == action.field_id
        )
        return action.model_copy(
            update={"message": build_next_field_question(field)}
        )

    if isinstance(action, ProposeAction):
        field = next(
            field for field in request.fields if field.id == action.field_id
        )
        question = truncate_text(field_question(field), 180).rstrip(" .?")
        display_value = (
            "Yes"
            if action.value is True
            else "No"
            if action.value is False
            else f'"{action.value}"'
        )
        return action.model_copy(
            update={
                "message": (
                    f'Got it — for “{question}”, I understood your answer '
                    f"as {display_value}. It is awaiting your confirmation "
                    "and has not been applied to the form."
                )
            }
        )

    if isinstance(action, SkipAction):
        field = next(
            field for field in request.fields if field.id == action.field_id
        )
        return action.model_copy(update={"message": _build_skip_message(field)})

    return action


def build_next_field_question(field: FormAgentField) -> str:
    question_text = field_question(field).rstrip(" .")
    if question_text.endswith("?"):
        question = question_text
    elif field.type == "dropdown":
        question = f"{question_text}. Which option applies to you?"
    elif field.type == "checkbox":
        question = f"{question_text}. Should this box be checked?"
    elif field.type == "number":
        question = f"{question_text}. What number should be entered here?"
    elif field.type == "textarea":
        question = f"{question_text}. What would you like to enter?"
    else:
        question = f"{question_text}. What should be entered here?"

    if field.type != "dropdown":
        return question

    options = field.options or []
    visible_options = [option[:120] for option in options[:8]]
    option_text = ", ".join(visible_options)
    if len(options) > len(visible_options):
        option_text += f", and {len(options) - len(visible_options)} more"
    return f"{question} Choose one of: {option_text}."


def _build_field_clarification(field: FormAgentField) -> ClarifyAction:
    question = truncate_text(field_question(field), 220)
    if field.type == "dropdown":
        visible_options = (field.options or [])[:8]
        options = ", ".join(visible_options)
        if len(field.options or []) > len(visible_options):
            options += f", and {len(field.options or []) - len(visible_options)} more"
        message = (
            f'I couldn\'t safely match that answer for “{question}” to an '
            f"available option. Please choose one of: {options}."
        )
    elif field.type == "checkbox":
        message = (
            f'For “{question}”, please answer yes or no so I know whether '
            "the box should be checked."
        )
    elif field.type == "number":
        message = (
            f'For “{question}”, please provide one exact numeric value to enter.'
        )
    else:
        message = (
            f'For “{question}”, please tell me the exact text you want entered.'
        )

    return ClarifyAction(
        action="clarify",
        message=message,
        field_id=field.id,
    )


def _build_skip_message(field: FormAgentField) -> str:
    question = truncate_text(field_question(field), 180).rstrip(" .?")
    return f'No problem — I\'ll leave “{question}” unanswered for now.'


def _asks_to_skip(message: str) -> bool:
    normalized_message = " ".join(message.strip().split())
    return any(
        pattern.fullmatch(normalized_message)
        for pattern in _SKIP_REQUEST_PATTERNS
    )


def _asks_for_unsupported_purpose(message: str) -> bool:
    normalized_message = message.strip()
    return any(
        pattern.search(normalized_message)
        for pattern in _PURPOSE_QUESTION_PATTERNS
    )
