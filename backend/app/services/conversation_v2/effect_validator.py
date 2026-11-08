from __future__ import annotations

import re

from app.services.form_agent.models import (
    AssistancePreferencesUpdatedAction,
    ClarifyAction,
    ConfirmedAction,
    ConversationAction,
    CorrectionStartedAction,
    FieldReopenedAction,
    FieldSelectedAction,
    FormAgentAction,
    FormAgentError,
    FormAgentRequest,
    ProposeAction,
    RejectedAction,
    ReplacementProposeAction,
    ReplacementRejectedAction,
    SkipAction,
    request_active_field_id,
    request_message,
)
from app.services.form_agent.value_normalizer import validate_field_value

from .models import (
    ChangeInputModeEffect,
    ConfirmProposalEffect,
    ConversationV2Decision,
    NoEffect,
    ProposeValueEffect,
    RejectProposalEffect,
    RequestGuidanceEffect,
    SelectFieldEffect,
    SkipFieldEffect,
    UpdateAssistanceEffect,
)
from .review_commands import is_explicit_confirmation


def validated_action(
    decision: ConversationV2Decision,
    request: FormAgentRequest,
) -> FormAgentAction:
    """Convert a model decision to one closed action without interpreting prose."""
    effect = decision.effect
    fields = {field.id: field for field in request.fields}
    active_id = request_active_field_id(request)
    pending = request.conversation_state.pending_proposal

    if isinstance(effect, (NoEffect, RequestGuidanceEffect)):
        if isinstance(effect, RequestGuidanceEffect) and effect.field_id not in fields:
            raise FormAgentError("Conversation Core returned an unknown field ID")
        if (
            isinstance(effect, NoEffect)
            and effect.awaiting == "clarification"
            and active_id is not None
        ):
            return ClarifyAction(
                action="clarify",
                message=decision.reply,
                field_id=active_id,
            )
        return ConversationAction(
            action="conversation",
            message=decision.reply,
            field_id=(effect.field_id if isinstance(effect, RequestGuidanceEffect) else active_id),
        )

    if isinstance(effect, ProposeValueEffect):
        field = fields.get(effect.field_id)
        if field is None:
            raise FormAgentError("Conversation Core returned an unknown field ID")
        try:
            validate_field_value(field.type, field.options, effect.value)
        except ValueError as error:
            raise FormAgentError(
                "Conversation Core returned a value that does not fit the field"
            ) from error
        original = effect.heard_value if effect.heard_value is not None else effect.value
        if field.status == "confirmed":
            return ReplacementProposeAction(
                action="replacement_propose",
                message=decision.reply,
                field_id=field.id,
                previous_confirmed_value=field.confirmed_value,
                original_value=original,
                value=effect.value,
            )
        if field.status == "skipped":
            raise FormAgentError("Conversation Core must reopen a skipped field first")
        if field.status != "unanswered":
            raise FormAgentError("Conversation Core proposed a value for a skipped field")
        return ProposeAction(
            action="propose",
            message=decision.reply,
            field_id=field.id,
            original_value=original,
            value=effect.value,
        )

    if isinstance(effect, ConfirmProposalEffect):
        if pending is None:
            raise FormAgentError("Conversation Core confirmed without a pending proposal")
        if not is_explicit_confirmation(request_message(request)):
            raise FormAgentError(
                "Conversation Core cannot confirm from ambiguous review language"
            )
        return ConfirmedAction(
            action="confirmed",
            message=decision.reply,
            field_id=pending.field_id,
            value=pending.value,
        )

    if isinstance(effect, RejectProposalEffect):
        if pending is None:
            raise FormAgentError("Conversation Core rejected without a pending proposal")
        if getattr(pending, "operation", None) == "replacement":
            return ReplacementRejectedAction(
                action="replacement_rejected",
                message=decision.reply,
                field_id=pending.field_id,
            )
        return RejectedAction(
            action="rejected",
            message=decision.reply,
            field_id=pending.field_id,
        )

    if isinstance(effect, SkipFieldEffect):
        field = fields.get(effect.field_id)
        if field is None:
            raise FormAgentError("Conversation Core returned an unknown field ID")
        if field.status not in {"unanswered", "skipped"}:
            raise FormAgentError("Conversation Core cannot skip a confirmed field")
        return SkipAction(
            action="skip",
            message=decision.reply,
            field_id=field.id,
        )

    if isinstance(effect, SelectFieldEffect):
        field = fields.get(effect.field_id)
        if field is None:
            raise FormAgentError("Conversation Core returned an unknown field ID")
        if field.status == "skipped":
            return FieldReopenedAction(
                action="field_reopened",
                message=decision.reply,
                field_id=field.id,
            )
        if field.status == "confirmed":
            return CorrectionStartedAction(
                action="correction_started",
                message=decision.reply,
                field_id=field.id,
            )
        return FieldSelectedAction(
            action="field_selected",
            message=decision.reply,
            field_id=field.id,
        )

    if isinstance(effect, ChangeInputModeEffect):
        preferences = request.assistance_preferences.model_copy(
            update={"interaction_mode": effect.mode}
        )
        first_unanswered = next(
            (field.id for field in request.fields if field.status == "unanswered"),
            None,
        )
        return AssistancePreferencesUpdatedAction(
            action="assistance_preferences_updated",
            message=decision.reply,
            preferences=preferences,
            introduction_status="saved",
            field_id=(
                first_unanswered
                if request.conversation_state.phase == "support_setup"
                else active_id
            ),
        )

    if isinstance(effect, UpdateAssistanceEffect):
        preferences = request.assistance_preferences.model_copy(
            update={"support_needs": effect.support_needs, "other_note": None}
        )
        return AssistancePreferencesUpdatedAction(
            action="assistance_preferences_updated",
            message=decision.reply,
            preferences=preferences,
            introduction_status=(
                "pending"
                if request.conversation_state.phase == "support_setup"
                else "saved"
            ),
            support_setup_step=(
                "interaction"
                if request.conversation_state.phase == "support_setup"
                else None
            ),
            field_id=(
                None
                if request.conversation_state.phase == "support_setup"
                else active_id
            ),
        )

    raise FormAgentError("Conversation Core returned an unsupported effect")


def validate_reply_effect_consistency(
    decision: ConversationV2Decision,
    request: FormAgentRequest,
) -> None:
    """Reject model wording that claims an unconfirmed mutation already happened."""
    if isinstance(decision.effect, (ConfirmProposalEffect, SkipFieldEffect)):
        return
    if isinstance(decision.effect, ProposeValueEffect):
        rendered_value = (
            "Yes"
            if decision.effect.value is True
            else "No"
            if decision.effect.value is False
            else decision.effect.value
        )
        if rendered_value.casefold() not in decision.reply.casefold():
            raise FormAgentError(
                "The proposal reply must read back the exact value that will be stored"
            )
        field = next(
            (item for item in request.fields if item.id == decision.effect.field_id),
            None,
        )
        heard_value = decision.effect.heard_value
        if (
            field is not None
            and field.options
            and isinstance(heard_value, str)
            and isinstance(decision.effect.value, str)
            and heard_value.casefold() != decision.effect.value.casefold()
            and not re.search(
                r"\b(?:option|match(?:ed|es)?|closest|mean(?:s|ing)?|sounds like)\b",
                decision.reply,
                re.IGNORECASE,
            )
        ):
            raise FormAgentError(
                "A transformed finite-choice proposal must explain that the user's "
                "wording maps to an available option"
            )
    mutation_claim = re.search(
        r"\bi(?:'ve| have)?\s+(?:recorded|entered|added|updated|changed)\b",
        decision.reply,
        re.IGNORECASE,
    )
    if mutation_claim:
        raise FormAgentError(
            "The reply claimed a form change that its effect did not apply"
        )
    if isinstance(decision.effect, NoEffect):
        pending = request.conversation_state.pending_proposal
        if pending is not None and re.search(
            r"\b(?:confirm(?:ed)?|is recorded|is added)\b",
            decision.reply,
            re.IGNORECASE,
        ):
            raise FormAgentError(
                "The reply claimed to confirm a proposal without a confirmation effect"
            )
        if re.search(
            r"\b(?:we(?:'ll| will)\s+skip|i(?:'ll| will)\s+skip)\b",
            decision.reply,
            re.IGNORECASE,
        ):
            raise FormAgentError(
                "The reply claimed to skip a field without a skip effect"
            )
