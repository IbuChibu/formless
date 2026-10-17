"""Validate conversation phases and materialize closed response effects."""

from __future__ import annotations

from typing import Optional

from pydantic import TypeAdapter

from .models import (
    AdvanceEvent,
    ClarifyAction,
    ConfirmedAction,
    ConfirmedEffect,
    CompletedEffect,
    ConversationAction,
    ConversationPhase,
    ConversationState,
    CorrectionCancelledAction,
    CorrectionCancelledEffect,
    CorrectionStartedAction,
    CorrectionStartedEffect,
    ExplainAction,
    FieldReopenedAction,
    FieldReopenedEffect,
    FieldSelectedAction,
    FieldSelectedEffect,
    FocusFieldEvent,
    FormAgentAction,
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    FormAgentResponse,
    FormAgentTransitionError,
    MessageEvent,
    NextAction,
    NoFormEffect,
    OfficialGuidanceCitation,
    PendingProposal,
    PendingReplacementProposal,
    ProposalEffect,
    ProposeAction,
    RememberedCandidate,
    RejectedAction,
    RejectedEffect,
    ReplacementProposalEffect,
    ReplacementProposeAction,
    ReplacementRejectedAction,
    SkipAction,
    SkippedEffect,
    WebGuidanceMetadata,
    request_active_field_id,
)
from .value_normalizer import validate_field_value


_RESPONSE_ADAPTER = TypeAdapter(FormAgentResponse)

_ALLOWED_EVENTS: dict[ConversationPhase, set[str]] = {
    "asking": {"advance", "message", "focus_field"},
    "awaiting_answer": {"message", "skip", "focus_field"},
    "awaiting_clarification": {"message", "skip", "focus_field"},
    "awaiting_confirmation": {
        "message",
        "confirm",
        "confirm_edit",
        "reject",
        "skip",
    },
    "awaiting_replacement": {
        "message",
        "cancel_correction",
    },
    "awaiting_replacement_confirmation": {
        "message",
        "confirm",
        "confirm_edit",
        "reject",
        "cancel_correction",
    },
    "field_confirmed": {"advance", "focus_field"},
    "field_skipped": {"advance", "focus_field"},
    "form_complete": {"message"},
}


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
    elif phase in {
        "awaiting_replacement",
        "awaiting_replacement_confirmation",
    }:
        if active_field is None or active_field.status != "confirmed":
            raise FormAgentTransitionError(
                "The confirmed field is no longer available for correction"
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
        raise FormAgentTransitionError("The form-complete state is stale")

    if phase in {
        "awaiting_confirmation",
        "awaiting_replacement_confirmation",
    }:
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
        if phase == "awaiting_replacement_confirmation":
            if not isinstance(pending, PendingReplacementProposal):
                raise FormAgentTransitionError(
                    "The pending replacement is unavailable"
                )
            if pending.previous_confirmed_value != active_field.confirmed_value:
                raise FormAgentTransitionError(
                    "The pending replacement is stale"
                )

    if isinstance(request.event, FocusFieldEvent):
        focused_field = fields_by_id[request.event.field_id]
        if focused_field.status != "unanswered":
            raise FormAgentTransitionError(
                "Only an unanswered field can become active"
            )


def response_for_action(
    action: FormAgentAction,
    request: FormAgentRequest,
    guidance: tuple[OfficialGuidanceCitation, ...] = (),
    web_guidance: Optional[WebGuidanceMetadata] = None,
    *,
    preserve_conversation_phase: bool = False,
) -> FormAgentResponse:
    active_field_id = request_active_field_id(request)
    remembered_candidates = request.conversation_state.remembered_candidates
    if isinstance(action, ProposeAction):
        state = ConversationState(
            phase="awaiting_confirmation",
            active_field_id=action.field_id,
            pending_proposal=PendingProposal(
                field_id=action.field_id,
                value=action.value,
            ),
            remembered_candidates=remembered_candidates,
        )
    elif isinstance(action, ReplacementProposeAction):
        state = ConversationState(
            phase="awaiting_replacement_confirmation",
            active_field_id=action.field_id,
            pending_proposal=PendingReplacementProposal(
                field_id=action.field_id,
                previous_confirmed_value=action.previous_confirmed_value,
                value=action.value,
            ),
            remembered_candidates=remembered_candidates,
        )
    elif isinstance(action, ConfirmedAction):
        state = _state_after_resolution(
            action.field_id,
            request.fields,
            remembered_candidates=_without_remembered_field(
                remembered_candidates,
                action.field_id,
            ),
        )
    elif isinstance(action, RejectedAction):
        state = ConversationState(
            phase="awaiting_answer",
            active_field_id=action.field_id,
            remembered_candidates=_without_remembered_field(
                remembered_candidates,
                action.field_id,
            ),
        )
    elif isinstance(action, ReplacementRejectedAction):
        state = _state_after_correction(
            request.fields,
            remembered_candidates=remembered_candidates,
        )
    elif isinstance(action, SkipAction):
        state = _state_after_resolution(
            action.field_id,
            request.fields,
            remembered_candidates=_without_remembered_field(
                remembered_candidates,
                action.field_id,
            ),
        )
    elif isinstance(action, NextAction):
        state = ConversationState(
            phase=("awaiting_answer" if action.field_id else "form_complete"),
            active_field_id=action.field_id,
            remembered_candidates=remembered_candidates,
        )
    elif isinstance(action, (FieldSelectedAction, FieldReopenedAction)):
        state = ConversationState(
            phase="awaiting_answer",
            active_field_id=action.field_id,
            remembered_candidates=remembered_candidates,
        )
    elif isinstance(action, CorrectionStartedAction):
        state = ConversationState(
            phase="awaiting_replacement",
            active_field_id=action.field_id,
            remembered_candidates=remembered_candidates,
        )
    elif isinstance(action, CorrectionCancelledAction):
        state = _state_after_correction(
            request.fields,
            remembered_candidates=remembered_candidates,
        )
    elif (
        isinstance(action, ClarifyAction)
        and request.conversation_state.phase
        in {"awaiting_confirmation", "awaiting_replacement_confirmation"}
        and isinstance(request.event, MessageEvent)
    ):
        state = request.conversation_state
    elif isinstance(action, ClarifyAction):
        if request.conversation_state.phase == "awaiting_replacement":
            state = request.conversation_state
        else:
            state = ConversationState(
                phase="awaiting_clarification",
                active_field_id=action.field_id,
                remembered_candidates=remembered_candidates,
            )
    elif isinstance(action, ConversationAction):
        state = request.conversation_state
    elif isinstance(action, ExplainAction) and (
        preserve_conversation_phase
        or request.conversation_state.phase
        in {
            "awaiting_answer",
            "awaiting_clarification",
            "awaiting_confirmation",
            "awaiting_replacement",
            "awaiting_replacement_confirmation",
        }
    ):
        state = request.conversation_state
    elif isinstance(action, ExplainAction):
        state = ConversationState(
            phase="awaiting_answer",
            active_field_id=action.field_id,
            remembered_candidates=remembered_candidates,
        )
    else:
        raise FormAgentError("Form Agent returned an unsupported action")

    if (
        not isinstance(request.event, AdvanceEvent)
        and active_field_id is not None
        and action.field_id not in {active_field_id, None}
        and not isinstance(
            action,
            (FieldSelectedAction, FieldReopenedAction, CorrectionStartedAction),
        )
    ):
        raise FormAgentError("Form Agent changed the active field unexpectedly")

    response = _RESPONSE_ADAPTER.validate_python(
        {
            "assistant_message": action.message,
            "effect": _effect_for_action(action),
            "conversation_state": state.model_dump(),
            "guidance": [citation.model_dump() for citation in guidance],
            "web_guidance": (
                web_guidance.model_dump()
                if web_guidance is not None
                else None
            ),
        }
    )
    return response.bind_internal_action(action)


def _effect_for_action(action: FormAgentAction) -> dict[str, object]:
    if isinstance(action, ProposeAction):
        return ProposalEffect(
            field_id=action.field_id,
            original_value=(
                action.original_value
                if action.original_value is not None
                else action.value
            ),
            prepared_value=action.value,
            transformation=action.transformation,
        ).model_dump()
    if isinstance(action, ReplacementProposeAction):
        return ReplacementProposalEffect(
            field_id=action.field_id,
            previous_confirmed_value=action.previous_confirmed_value,
            original_value=action.original_value,
            prepared_value=action.value,
            transformation=action.transformation,
        ).model_dump()
    if isinstance(action, ConfirmedAction):
        return ConfirmedEffect(
            field_id=action.field_id,
            value=action.value,
        ).model_dump()
    if isinstance(action, RejectedAction):
        return RejectedEffect(field_id=action.field_id).model_dump()
    if isinstance(action, ReplacementRejectedAction):
        return RejectedEffect(field_id=action.field_id).model_dump()
    if isinstance(action, SkipAction):
        return SkippedEffect(field_id=action.field_id).model_dump()
    if isinstance(action, NextAction):
        if action.field_id is None:
            return CompletedEffect().model_dump()
        return FieldSelectedEffect(field_id=action.field_id).model_dump()
    if isinstance(action, FieldSelectedAction):
        return FieldSelectedEffect(field_id=action.field_id).model_dump()
    if isinstance(action, FieldReopenedAction):
        return FieldReopenedEffect(field_id=action.field_id).model_dump()
    if isinstance(action, CorrectionStartedAction):
        return CorrectionStartedEffect(field_id=action.field_id).model_dump()
    if isinstance(action, CorrectionCancelledAction):
        return CorrectionCancelledEffect(field_id=action.field_id).model_dump()
    return NoFormEffect(field_id=action.field_id).model_dump()


def next_unanswered_field(
    fields: list[FormAgentField],
    *,
    resolved_field_id: Optional[str] = None,
) -> Optional[FormAgentField]:
    return next(
        (
            field
            for field in fields
            if field.status == "unanswered" and field.id != resolved_field_id
        ),
        None,
    )


def _state_after_resolution(
    resolved_field_id: str,
    fields: list[FormAgentField],
    *,
    remembered_candidates: list[RememberedCandidate],
) -> ConversationState:
    next_field = next_unanswered_field(
        fields,
        resolved_field_id=resolved_field_id,
    )
    return ConversationState(
        phase="awaiting_answer" if next_field else "form_complete",
        active_field_id=next_field.id if next_field else None,
        remembered_candidates=remembered_candidates,
    )


def _state_after_correction(
    fields: list[FormAgentField],
    *,
    remembered_candidates: list[RememberedCandidate],
) -> ConversationState:
    next_field = next_unanswered_field(fields)
    return ConversationState(
        phase="awaiting_answer" if next_field else "form_complete",
        active_field_id=next_field.id if next_field else None,
        remembered_candidates=remembered_candidates,
    )


def _without_remembered_field(
    candidates: list[RememberedCandidate],
    field_id: str,
) -> list[RememberedCandidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.field_id != field_id
    ]
