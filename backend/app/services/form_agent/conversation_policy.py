from __future__ import annotations

import re
from collections.abc import Callable
from typing import Optional

from pydantic import TypeAdapter

from .answer_adapters import (
    AnswerAdapterResult,
    ClarificationNeeded,
    MatchedAnswer,
    clarification_for_field,
    interpret_answer,
)
from .models import (
    AdvanceEvent,
    ClarifyAction,
    ConfirmEditEvent,
    ConfirmEvent,
    ConfirmedAction,
    ConversationPhase,
    ConversationState,
    ExplainAction,
    FocusFieldEvent,
    FormAgentAction,
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    FormAgentResponse,
    FormAgentTransitionError,
    MessageEvent,
    NextAction,
    PendingProposal,
    ProposeAction,
    RejectEvent,
    RejectedAction,
    SkipAction,
    SkipEvent,
    field_question,
    request_active_field_id,
    request_message,
    truncate_text,
)
from .value_normalizer import (
    canonicalize_field_value,
    validate_field_value,
)


_RESPONSE_ADAPTER = TypeAdapter(FormAgentResponse)

_ALLOWED_EVENTS: dict[ConversationPhase, set[str]] = {
    "asking": {"advance", "focus_field"},
    "awaiting_answer": {"message", "skip", "focus_field"},
    "awaiting_clarification": {"message", "skip", "focus_field"},
    "awaiting_confirmation": {
        "message",
        "confirm",
        "confirm_edit",
        "reject",
        "skip",
    },
    "field_confirmed": {"advance", "focus_field"},
    "field_skipped": {"advance", "focus_field"},
    "form_complete": set(),
}

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


def validate_event_transition(request: FormAgentRequest) -> None:
    phase = request.conversation_state.phase
    event_type = request.event.type
    if event_type not in _ALLOWED_EVENTS[phase]:
        raise FormAgentTransitionError(
            f'Event "{event_type}" is not valid while the conversation is '
            f'in phase "{phase}"'
        )

    fields_by_id = {field.id: field for field in request.fields}
    active_field_id = request.conversation_state.active_field_id
    active_field = (
        fields_by_id.get(active_field_id)
        if active_field_id is not None
        else None
    )

    if phase in {
        "awaiting_answer",
        "awaiting_clarification",
        "awaiting_confirmation",
    }:
        if active_field is None or active_field.status != "unanswered":
            raise FormAgentTransitionError(
                "The active field is no longer answerable"
            )
    elif phase == "field_confirmed":
        if active_field is None or active_field.status != "confirmed":
            raise FormAgentTransitionError(
                "The confirmed-field state is stale"
            )
    elif phase == "field_skipped":
        if active_field is None or active_field.status != "skipped":
            raise FormAgentTransitionError(
                "The skipped-field state is stale"
            )
    elif phase == "form_complete" and any(
        field.status == "unanswered" for field in request.fields
    ):
        raise FormAgentTransitionError(
            "The form-complete state is stale"
        )

    if phase == "awaiting_confirmation":
        pending = request.conversation_state.pending_proposal
        if pending is None or active_field is None:
            raise FormAgentTransitionError(
                "The pending proposal is unavailable"
            )
        try:
            validate_field_value(
                active_field.type,
                active_field.options,
                pending.value,
            )
        except ValueError as error:
            raise FormAgentTransitionError(
                "The pending proposal is no longer valid for its field"
            ) from error

    if isinstance(request.event, FocusFieldEvent):
        focused_field = fields_by_id[request.event.field_id]
        if focused_field.status != "unanswered":
            raise FormAgentTransitionError(
                "Only an unanswered field can become active"
            )


def unsupported_purpose_action(
    request: FormAgentRequest,
) -> Optional[ExplainAction]:
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        return None
    if not _asks_for_unsupported_purpose(request_message(request)):
        return None

    return ExplainAction(
        action="explain",
        message=(
            "The available form context explains what to provide, but it "
            "does not provide an authoritative reason why the organisation "
            "requests it. Check the form's official instructions or ask "
            "the organisation for that reason."
        ),
        field_id=active_field_id,
    )


def deterministic_action(
    request: FormAgentRequest,
    answer_interpreter: Callable[
        [FormAgentField, str],
        AnswerAdapterResult,
    ] = interpret_answer,
) -> Optional[FormAgentAction]:
    fields_by_id = {field.id: field for field in request.fields}
    active_field_id = request_active_field_id(request)
    active_field = (
        fields_by_id.get(active_field_id)
        if active_field_id is not None
        else None
    )
    event = request.event

    if isinstance(event, AdvanceEvent):
        return _next_unanswered_action(request.fields)

    if isinstance(event, ConfirmEvent):
        pending = request.conversation_state.pending_proposal
        if pending is None:
            raise FormAgentTransitionError(
                "There is no pending proposal to confirm"
            )
        return _confirmed_action(fields_by_id[pending.field_id], pending.value)

    if isinstance(event, ConfirmEditEvent):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active proposal to edit"
            )
        try:
            value = canonicalize_field_value(
                active_field.type,
                active_field.options,
                event.value,
            )
            validate_field_value(
                active_field.type,
                active_field.options,
                value,
            )
        except ValueError as error:
            raise FormAgentTransitionError(
                "The edited answer is not valid for this field"
            ) from error
        return _confirmed_action(active_field, value)

    if isinstance(event, RejectEvent):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active proposal to reject"
            )
        return RejectedAction(
            action="rejected",
            message=(
                "No problem — I haven’t used that proposal. Tell me what "
                "you’d like to enter instead."
            ),
            field_id=active_field.id,
        )

    if isinstance(event, SkipEvent):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active field to skip"
            )
        return SkipAction(
            action="skip",
            message=_build_skip_message(active_field),
            field_id=active_field.id,
        )

    if (
        request.conversation_state.phase == "awaiting_confirmation"
        and isinstance(event, MessageEvent)
    ):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active proposal to review"
            )
        return ClarifyAction(
            action="clarify",
            message=(
                "That proposal is still awaiting confirmation. Use Confirm, "
                "Edit, Reject, or Skip field before sending another answer."
            ),
            field_id=active_field.id,
        )

    if active_field is None or active_field.status != "unanswered":
        return None

    message = request_message(request)
    if _asks_to_skip(message):
        return SkipAction(
            action="skip",
            message=_build_skip_message(active_field),
            field_id=active_field.id,
        )

    adapter_result = answer_interpreter(active_field, message)
    if isinstance(adapter_result, ClarificationNeeded):
        return _adapter_clarification(active_field, adapter_result)
    if not isinstance(adapter_result, MatchedAnswer):
        return None

    return normalize_action_message(
        ProposeAction(
            action="propose",
            message="Proposal awaiting confirmation.",
            field_id=active_field.id,
            value=adapter_result.value,
        ),
        request,
    )


def response_for_action(
    action: FormAgentAction,
    request: FormAgentRequest,
) -> FormAgentResponse:
    active_field_id = request_active_field_id(request)
    if isinstance(action, ProposeAction):
        state = ConversationState(
            phase="awaiting_confirmation",
            active_field_id=action.field_id,
            pending_proposal=PendingProposal(
                field_id=action.field_id,
                value=action.value,
            ),
        )
    elif isinstance(action, ConfirmedAction):
        state = ConversationState(
            phase="field_confirmed",
            active_field_id=action.field_id,
        )
    elif isinstance(action, RejectedAction):
        state = ConversationState(
            phase="awaiting_answer",
            active_field_id=action.field_id,
        )
    elif isinstance(action, SkipAction):
        state = ConversationState(
            phase="field_skipped",
            active_field_id=action.field_id,
        )
    elif isinstance(action, NextAction):
        state = ConversationState(
            phase=("awaiting_answer" if action.field_id else "form_complete"),
            active_field_id=action.field_id,
        )
    elif (
        isinstance(action, ClarifyAction)
        and request.conversation_state.phase == "awaiting_confirmation"
        and isinstance(request.event, MessageEvent)
    ):
        state = request.conversation_state
    elif isinstance(action, ClarifyAction):
        state = ConversationState(
            phase="awaiting_clarification",
            active_field_id=action.field_id,
        )
    elif isinstance(action, ExplainAction):
        state = ConversationState(
            phase="awaiting_answer",
            active_field_id=action.field_id,
        )
    else:
        raise FormAgentError("Form Agent returned an unsupported action")

    if (
        not isinstance(request.event, AdvanceEvent)
        and active_field_id is not None
        and action.field_id not in {active_field_id, None}
    ):
        raise FormAgentError("Form Agent changed the active field unexpectedly")

    return _RESPONSE_ADAPTER.validate_python(
        {"action": action.model_dump(), "conversation_state": state.model_dump()}
    )


def invalid_value_clarification(
    error: FormAgentError,
    request: FormAgentRequest,
) -> Optional[ClarifyAction]:
    if str(error) != "Form Agent returned an invalid proposal value":
        return None
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        return None

    field = next(
        (field for field in request.fields if field.id == active_field_id),
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
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        return None

    field = next(
        (field for field in request.fields if field.id == active_field_id),
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


def _next_unanswered_action(fields: list[FormAgentField]) -> NextAction:
    next_field = next(
        (field for field in fields if field.status == "unanswered"),
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


def _confirmed_action(
    field: FormAgentField,
    value: str | bool,
) -> ConfirmedAction:
    question = truncate_text(field_question(field), 180).rstrip(" .?")
    return ConfirmedAction(
        action="confirmed",
        message=(
            f'Confirmed — I added {format_agent_value(value)} to “{question}”. '
            "Continue when you’re ready."
        ),
        field_id=field.id,
        value=value,
    )


def _build_field_clarification(field: FormAgentField) -> ClarifyAction:
    return _adapter_clarification(field, clarification_for_field(field))


def _adapter_clarification(
    field: FormAgentField,
    clarification: ClarificationNeeded,
) -> ClarifyAction:
    question = truncate_text(field_question(field), 220)
    return ClarifyAction(
        action="clarify",
        message=(
            f'For “{question}”: {clarification.reason} '
            f"{clarification.accepted_shape}"
        ),
        field_id=field.id,
    )


def _build_skip_message(field: FormAgentField) -> str:
    question = truncate_text(field_question(field), 180).rstrip(" .?")
    return f'No problem — I\'ll leave “{question}” unanswered for now.'


def format_agent_value(value: str | bool) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return f'"{value}"'


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
