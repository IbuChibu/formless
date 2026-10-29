from __future__ import annotations

import re
from collections.abc import Callable
from typing import Optional

from .answer_preparation import prepare_proposal_action
from .candidate_constraints import CandidateConstraintViolation
from .assistance_policy import assistance_preference_action
from .answer_adapters import (
    AnswerAdapterResult,
    ClarificationNeeded,
    MatchedAnswer,
    interpret_answer,
    recover_prior_answer,
    remembered_answer,
)
from .action_validation import (
    LOST_ACTIVE_FIELD_ERROR as _LOST_ACTIVE_FIELD_ERROR,
    REPEATED_EXPLANATION_ERROR as _REPEATED_EXPLANATION_ERROR,
    UNRELATED_WORKFLOW_ERROR as _UNRELATED_WORKFLOW_ERROR,
    UNSUPPORTED_FORMAT_CLAIM_ERROR as _UNSUPPORTED_FORMAT_CLAIM_ERROR,
)
from .models import (
    AdvanceEvent,
    CancelCorrectionEvent,
    ClarifyAction,
    ConfirmEditEvent,
    ConfirmEvent,
    ConversationAction,
    ExplainAction,
    FormAgentAction,
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    FormAgentTransitionError,
    MessageEvent,
    NextAction,
    PendingReplacementProposal,
    ProposeAction,
    RejectEvent,
    RejectedAction,
    ReplacementProposeAction,
    ReplacementRejectedAction,
    SkipAction,
    SkipEvent,
    WebGuidanceMetadata,
    field_question,
    request_active_field_id,
    request_message,
    truncate_text,
)
from .field_navigation import navigation_decision
from .intent_policy import (
    TurnIntent,
    _comparison_words,
    classify_turn_intent,
)
from .navigation_policy import (
    active_field_return_anchor as _active_field_return_anchor,
    active_field_side_question_action as _active_field_side_question_action,
    adapter_clarification as _adapter_clarification,
    build_field_clarification as _build_field_clarification,
    build_next_field_question,
    completed_conversation_action as _completed_conversation_action,
    confirmed_action as _confirmed_action,
    correction_cancelled_action as _correction_cancelled_action,
    format_agent_value,
    navigation_action as _navigation_action,
    next_unanswered_action as _next_unanswered_action,
    progress_action as _progress_action,
    progression_message as _progression_message,
    skip_action as _skip_action,
    start_conversation_action as _start_conversation_action,
)
from .state_machine import next_unanswered_field as _next_unanswered_field
from .value_normalizer import (
    canonicalize_field_value,
    validate_field_value,
)


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

def explanation_repair_fallback(
    error: FormAgentError,
    request: FormAgentRequest,
    turn_intent_override: Optional[TurnIntent] = None,
) -> Optional[ExplainAction]:
    if str(error) not in {
        _REPEATED_EXPLANATION_ERROR,
        _UNRELATED_WORKFLOW_ERROR,
        _LOST_ACTIVE_FIELD_ERROR,
        _UNSUPPORTED_FORMAT_CLAIM_ERROR,
    }:
        return None
    if (
        turn_intent_override or classify_turn_intent(request)
    ) != "wording_clarification":
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

    question = truncate_text(field_question(field), 220).rstrip(" .?")
    if str(error) == _UNSUPPORTED_FORMAT_CLAIM_ERROR:
        subject = truncate_text(field.label, 220).rstrip(" .?")
        message = (
            f"This is asking for {subject}. The form text available to me "
            "does not specify a required date format, so I won't invent one."
        )
    elif str(error) == _LOST_ACTIVE_FIELD_ERROR:
        message = (
            f'Let me stay with the question “{question}”. Which part of '
            "that wording would you like me to explain differently? Your "
            "form answer has not changed."
        )
    else:
        message = (
            "I don't want to repeat the same explanation. Which word or "
            f'phrase in “{question}” is unclear? Tell me that part and I’ll '
            "explain just that. Your form answer has not changed."
        )
    return ExplainAction(
        action="explain",
        message=message,
        field_id=field.id,
    )


def model_failure_fallback(
    request: FormAgentRequest,
    turn_intent_override: Optional[TurnIntent] = None,
) -> Optional[FormAgentAction]:
    """Keep a failed model turn useful without granting it a form effect."""
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        return None
    field = next(
        (field for field in request.fields if field.id == active_field_id),
        None,
    )
    if field is None:
        return None

    intent = turn_intent_override or classify_turn_intent(request)
    message = request_message(request)
    question = truncate_text(field_question(field), 220).rstrip(" .?")

    if intent == "general_conversation":
        if re.search(r"\b(?:pause|wait|stop)\b", message, re.IGNORECASE):
            reply = (
                "Of course — we can pause here. Nothing on the form has "
                "changed, and we can continue whenever you're ready."
            )
        else:
            reply = (
                "I couldn't answer that clearly, but nothing on the form "
                f'has changed. We are still on “{question}”; you can rephrase '
                "your message or continue when you're ready."
            )
        return ConversationAction(
            action="conversation",
            message=reply,
            field_id=field.id,
        )

    if intent == "wording_clarification":
        return ExplainAction(
            action="explain",
            message=(
                f'Let me stay with “{question}”. Which word or part would '
                "you like explained differently? Nothing on the form has "
                "changed."
            ),
            field_id=field.id,
        )

    if intent == "evidence_question":
        return ExplainAction(
            action="explain",
            message=(
                "I couldn't produce a reliable explanation from the "
                "available guidance, so I won't guess. Check the form's "
                "instructions or issuing organisation; your answer has not "
                "changed."
            ),
            field_id=field.id,
        )

    if intent == "prose_polish":
        return ClarifyAction(
            action="clarify",
            message=(
                "I couldn't prepare a wording suggestion safely, so I left "
                "your answer unchanged. You can rephrase the request or use "
                "your original wording."
            ),
            field_id=field.id,
        )

    return _build_field_clarification(field)


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
    turn_intent = classify_turn_intent(request)

    assistance_action = assistance_preference_action(request)
    if assistance_action is not None:
        return assistance_action

    if isinstance(event, AdvanceEvent):
        return _next_unanswered_action(request.fields)

    if isinstance(event, CancelCorrectionEvent):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active correction to cancel"
            )
        return _correction_cancelled_action(active_field, request.fields)

    if isinstance(event, MessageEvent) and active_field is not None:
        side_question_action = _active_field_side_question_action(
            request,
            active_field,
        )
        if side_question_action is not None:
            return side_question_action

    if isinstance(event, MessageEvent):
        navigation = navigation_decision(event.content, request.fields)
        if navigation is not None:
            navigation_action = _navigation_action(navigation, request)
            if navigation_action is not None:
                return navigation_action

    if (
        request.conversation_state.phase == "asking"
        and isinstance(event, MessageEvent)
    ):
        return _start_conversation_action(request.fields)

    if (
        request.conversation_state.phase == "form_complete"
        and isinstance(event, MessageEvent)
    ):
        return _completed_conversation_action(request)

    if isinstance(event, ConfirmEvent):
        pending = request.conversation_state.pending_proposal
        if pending is None:
            raise FormAgentTransitionError(
                "There is no pending proposal to confirm"
            )
        return _confirmed_action(
            fields_by_id[pending.field_id],
            pending.value,
            request.fields,
            replacement=isinstance(pending, PendingReplacementProposal),
        )

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
        return _confirmed_action(
            active_field,
            value,
            request.fields,
            replacement=(
                request.conversation_state.phase
                == "awaiting_replacement_confirmation"
            ),
            edited=True,
        )

    if isinstance(event, RejectEvent):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active proposal to reject"
            )
        question = truncate_text(
            field_question(active_field),
            180,
        ).rstrip(" .?")
        if (
            request.conversation_state.phase
            == "awaiting_replacement_confirmation"
        ):
            return ReplacementRejectedAction(
                action="replacement_rejected",
                message=(
                    "No change made — the current answer for "
                    f'“{question}” remains '
                    f"{format_agent_value(active_field.confirmed_value)}. "
                    f"{_progression_message(_next_unanswered_field(request.fields))}"
                ),
                field_id=active_field.id,
            )
        return RejectedAction(
            action="rejected",
            message=(
                "No problem — I haven’t used that proposal. What should be "
                f'entered instead for “{question}”?'
            ),
            field_id=active_field.id,
        )

    if isinstance(event, SkipEvent):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active field to skip"
            )
        if event.field_id != active_field.id:
            raise FormAgentTransitionError(
                "The field selected for skipping is no longer active"
            )
        return _skip_action(active_field, request.fields)

    if (
        request.conversation_state.phase
        in {"awaiting_confirmation", "awaiting_replacement_confirmation"}
        and isinstance(event, MessageEvent)
    ):
        if active_field is None:
            raise FormAgentTransitionError(
                "There is no active proposal to review"
            )
        if turn_intent == "progress_question":
            return _progress_action(request, active_field)
        if turn_intent in {
            "wording_clarification",
            "evidence_question",
        }:
            return None
        if turn_intent == "general_conversation":
            return ConversationAction(
                action="conversation",
                message=(
                    "Got it. The proposal is still waiting for your review, "
                    "and nothing has been added to the form."
                ),
                field_id=active_field.id,
            )
        correction_copy = (
            "That replacement is still awaiting confirmation. Use Confirm, "
            "Edit, Reject, or Cancel correction before sending another answer."
            if request.conversation_state.phase
            == "awaiting_replacement_confirmation"
            else "That proposal is still awaiting confirmation. Use Confirm, "
            "Edit, Reject, or Skip field before sending another answer."
        )
        return ClarifyAction(
            action="clarify",
            message=correction_copy,
            field_id=active_field.id,
        )

    is_replacement = (
        request.conversation_state.phase == "awaiting_replacement"
    )
    expected_status = "confirmed" if is_replacement else "unanswered"
    if active_field is None or active_field.status != expected_status:
        return None

    message = request_message(request)
    if not is_replacement and _asks_to_skip(message):
        return _skip_action(active_field, request.fields)

    if turn_intent == "progress_question":
        return _progress_action(request, active_field)
    if turn_intent in {
        "wording_clarification",
        "evidence_question",
        "general_conversation",
        "prose_polish",
    }:
        return None

    adapter_result = remembered_answer(
        active_field,
        message,
        request.conversation_state.remembered_candidates,
    )
    if adapter_result is None:
        adapter_result = recover_prior_answer(
            active_field,
            message,
            request.history,
        )
    if adapter_result is None:
        adapter_result = answer_interpreter(active_field, message)
    if isinstance(adapter_result, ClarificationNeeded):
        return _adapter_clarification(active_field, adapter_result)
    if not isinstance(adapter_result, MatchedAnswer):
        return None

    try:
        proposal = prepare_proposal_action(
            ProposeAction(
                action="propose",
                message="Proposal awaiting confirmation.",
                field_id=active_field.id,
                value=adapter_result.value,
                original_value=adapter_result.original_value,
            ),
            request,
        )
    except CandidateConstraintViolation as error:
        return _adapter_clarification(
            active_field,
            ClarificationNeeded(
                reason=error.failure.reason,
                accepted_shape=error.failure.accepted_shape,
            ),
        )
    if is_replacement:
        replacement = ReplacementProposeAction(
            action="replacement_propose",
            message=proposal.message,
            field_id=proposal.field_id,
            previous_confirmed_value=active_field.confirmed_value,
            value=proposal.value,
            original_value=(
                proposal.original_value
                if proposal.original_value is not None
                else proposal.value
            ),
            transformation=proposal.transformation,
        )
        return normalize_action_message(replacement, request)
    return normalize_action_message(proposal, request)


def insufficient_guidance_action(
    request: FormAgentRequest,
    web_guidance: WebGuidanceMetadata,
) -> ExplainAction:
    if web_guidance.status not in {"empty", "unavailable"}:
        raise FormAgentError(
            "Insufficient-guidance response requires empty or unavailable "
            "web guidance"
        )
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        raise FormAgentError("Web guidance requires an active field")

    subject = {
        "meaning": "a verified meaning for this question",
        "purpose": "the purpose of this question",
        "requirements": "an authoritative requirement or rule for this question",
        "where_to_find": "a verified place to find this information",
    }[web_guidance.topic]
    opening = (
        "I couldn't check live guidance right now."
        if web_guidance.status == "unavailable"
        else "I couldn't find relevant verified guidance for this question."
    )
    return ExplainAction(
        action="explain",
        message=(
            f"{opening} The form wording alone does not establish {subject}, "
            "so I won't guess. You can retry the guidance check, consult the "
            "form's instructions or issuing organisation, answer from your "
            "own knowledge, or skip this field for now."
        ),
        field_id=active_field_id,
    )


def conflicting_guidance_action(
    request: FormAgentRequest,
    web_guidance: WebGuidanceMetadata,
) -> ExplainAction:
    if web_guidance.status != "conflicting":
        raise FormAgentError(
            "Conflict response requires conflicting web guidance"
        )
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        raise FormAgentError("Web guidance requires an active field")

    return ExplainAction(
        action="explain",
        message=(
            "The relevant live sources disagree about whether this question "
            "is required or optional, so I cannot give a definitive rule. "
            "Review the linked sources and check the issuing organisation's "
            "instructions. Your form answer has not been changed."
        ),
        field_id=active_field_id,
    )


def invalid_value_clarification(
    error: FormAgentError,
    request: FormAgentRequest,
) -> Optional[ClarifyAction]:
    if not isinstance(error, CandidateConstraintViolation) and str(error) != (
        "Form Agent returned an invalid proposal value"
    ):
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

    if isinstance(error, CandidateConstraintViolation):
        return _adapter_clarification(
            field,
            ClarificationNeeded(
                reason=error.failure.reason,
                accepted_shape=error.failure.accepted_shape,
            ),
        )
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
    turn_intent_override: Optional[TurnIntent] = None,
    *,
    preserve_message: bool = False,
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
        if preserve_message:
            return action
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
        if action.transformation:
            original_display = format_agent_value(
                action.original_value
                if action.original_value is not None
                else action.value
            )
            if isinstance(action.original_value, str):
                original_display = format_agent_value(
                    action.original_value.rstrip(".!?")
                )
            message = (
                f"You said {original_display}. I prepared {display_value} "
                f'for “{question}”. {action.transformation} Please review '
                "and confirm it before I add it to the form."
            )
        else:
            message = (
                f'I heard {display_value} for “{question}”. Please review '
                "and confirm it before I add it to the form."
            )
        return action.model_copy(update={"message": message})

    if isinstance(action, ReplacementProposeAction):
        if preserve_message:
            return action
        field = next(
            field for field in request.fields if field.id == action.field_id
        )
        question = truncate_text(field_question(field), 180).rstrip(" .?")
        previous = format_agent_value(action.previous_confirmed_value)
        original = format_agent_value(action.original_value)
        prepared = format_agent_value(action.value)
        transformation = (
            f" {action.transformation}" if action.transformation else ""
        )
        return action.model_copy(
            update={
                "message": (
                    f'The current answer for “{question}” is {previous}. '
                    f"You said {original}; I prepared {prepared} for review."
                    f"{transformation} Explicitly confirm it before I replace "
                    "the current answer."
                )
            }
        )

    if (
        isinstance(action, ExplainAction)
        and (
            turn_intent_override or classify_turn_intent(request)
        ) == "wording_clarification"
    ):
        field = next(
            (
                field
                for field in request.fields
                if field.id == action.field_id
            ),
            None,
        )
        if field is not None:
            anchor = _active_field_return_anchor(field)
            if anchor not in set(_comparison_words(action.message)):
                return action.model_copy(
                    update={
                        "message": truncate_text(
                            f"{action.message.rstrip()} We’re still on the "
                            f"{anchor} question.",
                            4000,
                        )
                    }
                )

    if isinstance(action, SkipAction):
        field = next(
            field for field in request.fields if field.id == action.field_id
        )
        return _skip_action(field, request.fields)

    return action


def _asks_to_skip(message: str) -> bool:
    normalized_message = " ".join(message.strip().split())
    return any(
        pattern.fullmatch(normalized_message)
        for pattern in _SKIP_REQUEST_PATTERNS
    )
