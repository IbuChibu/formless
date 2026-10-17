"""Build deterministic navigation, progression, and clarification actions."""

from __future__ import annotations

import re
from typing import Literal, Optional

from .answer_adapters import ClarificationNeeded, clarification_for_field
from .field_navigation import NavigationDecision
from .intent_policy import classify_turn_intent
from .models import (
    ClarifyAction,
    ConfirmedAction,
    ConversationAction,
    CorrectionCancelledAction,
    CorrectionStartedAction,
    ExplainAction,
    FieldReopenedAction,
    FieldSelectedAction,
    FormAgentAction,
    FormAgentField,
    FormAgentRequest,
    NextAction,
    SkipAction,
    field_question,
    request_message,
    truncate_text,
)
from .state_machine import next_unanswered_field as _next_unanswered_field


_COUNT_SELF_QUESTION_PATTERN = re.compile(
    r"\b(?:do|should|can)\s+i\s+(?:count|include)\s+myself\b|"
    r"\b(?:count|include)\s+me\b",
    re.IGNORECASE,
)
_COUNT_SELF_CONTEXT_PATTERN = re.compile(
    r"\b(?:count|include)\s+(?:yourself|the\s+applicant)\b",
    re.IGNORECASE,
)
_FRUSTRATION_PATTERN = re.compile(
    r"\b(?:exhausting|frustrating|overwhelming|fed\s+up)\b",
    re.IGNORECASE,
)
_SIMPLE_REPHRASE_PATTERN = re.compile(
    r"\b(?:make\s+(?:that|this|it)\s+(?:even\s+)?simpler|"
    r"ask\s+me\s+normally|"
    r"ask\s+(?:me\s+)?(?:that|this|it)\s+(?:normally|in\s+simpler\s+words)|"
    r"ask\s+the\s+question\s+in\s+(?:one\s+)?simple\s+sentence)\b",
    re.IGNORECASE,
)


def active_field_return_anchor(field: FormAgentField) -> str:
    metadata = " ".join(
        value
        for value in (field.id, field.label, field.question, field.help_text)
        if value
    ).casefold()
    for pattern, anchor in (
        (r"\b(?:address|residen|postcode|postal)\b", "address"),
        (r"\b(?:date|day|month|year|when)\b", "date"),
        (r"\b(?:name|surname)\b", "name"),
        (r"\b(?:budget|planned)\b", "budget"),
        (r"\b(?:income|earn|salary|wage)\b", "income"),
        (r"\b(?:count|number|people|persons?)\b", "people"),
    ):
        if re.search(pattern, metadata) is not None:
            return anchor
    return truncate_text(field_display_name(field).casefold(), 80)


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


def active_field_side_question_action(
    request: FormAgentRequest,
    field: FormAgentField,
) -> Optional[ConversationAction]:
    message = request_message(request)
    if _FRUSTRATION_PATTERN.search(message) is not None:
        return ConversationAction(
            action="conversation",
            message=(
                "I understand — that wording is frustrating. In plain "
                f"language: {_plain_language_question(field)}"
            ),
            field_id=field.id,
        )
    if _SIMPLE_REPHRASE_PATTERN.search(message) is not None:
        return ConversationAction(
            action="conversation",
            message=f"In simpler words: {_plain_language_question(field)}",
            field_id=field.id,
        )
    if _COUNT_SELF_QUESTION_PATTERN.search(message) is None:
        return None
    metadata = " ".join(
        value
        for value in (
            field.id,
            field.label,
            field.question,
            field.help_text,
        )
        if value
    )
    if _COUNT_SELF_CONTEXT_PATTERN.search(metadata) is None:
        return None
    question = field_display_name(field)
    return ConversationAction(
        action="conversation",
        message=(
            "Yes — this question says to count yourself. If you live alone, "
            f'the count is 1. We are still on “{question}”; what exact count '
            "would you like to use?"
        ),
        field_id=field.id,
    )


def _plain_language_question(field: FormAgentField) -> str:
    metadata = " ".join(
        value
        for value in (
            field.id,
            field.label,
            field.question,
            field.help_text,
        )
        if value
    ).casefold()
    if re.search(
        r"\b(?:occupancy|commenced|started\s+living|move.?in)\b",
        metadata,
    ):
        return "When did you start living at your current home?"
    if "preferred" in metadata or "name you want" in metadata:
        return "What name would you like us to use?"
    if re.search(r"\b(?:what happened|help you need|already tried)\b", metadata):
        return (
            "What happened, what help do you need, and what have you already "
            "tried?"
        )
    return build_next_field_question(field)


def navigation_action(
    decision: NavigationDecision,
    request: FormAgentRequest,
) -> Optional[FormAgentAction]:
    phase = request.conversation_state.phase
    active_field_id = request.conversation_state.active_field_id

    if decision.kind == "cancel_correction":
        if phase not in {
            "awaiting_replacement",
            "awaiting_replacement_confirmation",
        }:
            return ConversationAction(
                action="conversation",
                message="There is no active correction to cancel.",
                field_id=active_field_id,
            )
        field = next(
            field
            for field in request.fields
            if field.id == active_field_id
        )
        return correction_cancelled_action(field, request.fields)

    if decision.kind == "review_statuses":
        if (
            active_field_id is not None
            and classify_turn_intent(request) == "progress_question"
        ):
            active_field = next(
                field
                for field in request.fields
                if field.id == active_field_id
            )
            return progress_action(request, active_field)
        return ConversationAction(
            action="conversation",
            message=status_review_message(request.fields, decision.statuses),
            field_id=active_field_id,
        )

    if decision.kind == "review_value":
        if len(decision.matches) == 1:
            field = decision.matches[0]
            return ConversationAction(
                action="conversation",
                message=(
                    f'Your confirmed answer for “{field_display_name(field)}” '
                    f"is {format_agent_value(field.confirmed_value)}. Nothing "
                    "on the form has changed."
                ),
                field_id=active_field_id,
            )
        return ConversationAction(
            action="conversation",
            message=field_match_clarification(
                decision.matches,
                "confirmed question",
            ),
            field_id=active_field_id,
        )

    if phase in {
        "awaiting_confirmation",
        "awaiting_replacement_confirmation",
    }:
        return ConversationAction(
            action="conversation",
            message=(
                "Please resolve the answer awaiting confirmation first. "
                "No field or value has changed."
            ),
            field_id=active_field_id,
        )

    if len(decision.matches) != 1:
        required_kind = {
            "select": "unanswered question",
            "reopen": "skipped question",
            "correct": "confirmed question",
        }[decision.kind]
        return ConversationAction(
            action="conversation",
            message=field_match_clarification(
                decision.matches,
                required_kind,
            ),
            field_id=active_field_id,
        )

    field = decision.matches[0]
    if decision.kind == "select":
        return FieldSelectedAction(
            action="field_selected",
            message=f"Okay — {build_next_field_question(field)}",
            field_id=field.id,
        )
    if decision.kind == "reopen":
        return FieldReopenedAction(
            action="field_reopened",
            message=(
                f'I reopened “{field_display_name(field)}”. '
                f"{build_next_field_question(field)}"
            ),
            field_id=field.id,
        )
    if decision.kind == "correct":
        return CorrectionStartedAction(
            action="correction_started",
            message=(
                f'Your current confirmed answer for “{field_display_name(field)}” '
                f"is {format_agent_value(field.confirmed_value)}. It will stay "
                "on the form unless you explicitly confirm a replacement. "
                "What should the replacement be?"
            ),
            field_id=field.id,
        )
    return None


def correction_cancelled_action(
    field: FormAgentField,
    fields: list[FormAgentField],
) -> CorrectionCancelledAction:
    next_field = _next_unanswered_field(fields)
    return CorrectionCancelledAction(
        action="correction_cancelled",
        message=(
            f'Correction cancelled. Your confirmed answer for '
            f'“{field_display_name(field)}” remains '
            f"{format_agent_value(field.confirmed_value)}. "
            f"{progression_message(next_field)}"
        ),
        field_id=field.id,
    )


def status_review_message(
    fields: list[FormAgentField],
    statuses: tuple[Literal["unanswered", "confirmed", "skipped"], ...],
) -> str:
    labels = {
        "confirmed": "Confirmed",
        "skipped": "Skipped",
        "unanswered": "Unanswered",
    }
    sections: list[str] = []
    for status in statuses:
        matching = [field for field in fields if field.status == status]
        visible = matching[:6]
        names = "; ".join(
            (
                f"{field_display_name(field)} is "
                f"{format_agent_value(field.confirmed_value)}"
                if status == "confirmed"
                else field_display_name(field)
            )
            for field in visible
        )
        if len(matching) > len(visible):
            names += f"; and {len(matching) - len(visible)} more"
        sections.append(
            f"{labels[status]} ({len(matching)}): {names or 'none'}"
        )
    return ". ".join(sections) + ". Nothing on the form has changed."


def field_match_clarification(
    matches: tuple[FormAgentField, ...],
    required_kind: str,
) -> str:
    if not matches:
        return (
            f"I couldn't match that reference to a {required_kind}. "
            "Please use wording from the question or its visible label. "
            "Nothing on the form has changed."
        )
    visible = matches[:4]
    options = "; ".join(field_display_name(field) for field in visible)
    remainder = (
        f"; and {len(matches) - len(visible)} more"
        if len(matches) > len(visible)
        else ""
    )
    return (
        f"I found more than one matching {required_kind}: {options}{remainder}. "
        "Which one did you mean? Nothing on the form has changed."
    )


def field_display_name(field: FormAgentField) -> str:
    return truncate_text(field_question(field), 180).rstrip(" .?")


def next_unanswered_action(fields: list[FormAgentField]) -> NextAction:
    next_field = _next_unanswered_field(fields)
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


def start_conversation_action(fields: list[FormAgentField]) -> NextAction:
    action = next_unanswered_action(fields)
    if action.field_id is None:
        return action
    return action.model_copy(
        update={
            "message": (
                "I can help you work through this form one question at a "
                f"time. Let's start here: {action.message}"
            )
        }
    )


def completed_conversation_action(
    request: FormAgentRequest,
) -> ConversationAction:
    fields = request.fields
    message = request_message(request)
    normalized = message.casefold()
    confirmed_fields = [
        field
        for field in fields
        if field.status == "confirmed" and field.confirmed_value is not None
    ]
    skipped_fields = [field for field in fields if field.status == "skipped"]
    unanswered_fields = [
        field for field in fields if field.status == "unanswered"
    ]

    if re.search(r"\b(?:skip|skipped)\b", normalized):
        response = status_review_message(fields, ("skipped",))
    elif re.search(r"\b(?:unanswered|remaining|left)\b", normalized):
        response = status_review_message(fields, ("unanswered",))
    elif re.search(
        r"\b(?:read|recap|summari[sz]e)\b.*\b(?:back|answers?|values?|details?)\b|"
        r"\b(?:tell|give)\s+me\b.*\b(?:entered|answers?|values?|details?)\b|"
        r"\bwhat\s+(?:did|have)\s+we\s+(?:enter|entered|put|confirmed?)\b",
        normalized,
    ):
        response = _confirmed_values_summary(confirmed_fields)
    elif re.search(r"\bdid\s+you\s+keep\b", normalized):
        longest = max(
            confirmed_fields,
            key=lambda field: len(str(field.confirmed_value)),
            default=None,
        )
        response = (
            "Yes — I kept your confirmed answer"
            + (
                f" for {field_display_name(longest)}: "
                f"{format_agent_value(longest.confirmed_value)}."
                if longest is not None
                else "."
            )
            + " Nothing on the form has changed."
        )
    elif re.search(r"\b(?:complete|completed|finished|all\s+three)\b", normalized):
        response = (
            f"Yes — this section is complete: {len(confirmed_fields)} "
            f"confirmed, {len(skipped_fields)} skipped, and "
            f"{len(unanswered_fields)} unanswered."
        )
    elif re.search(r"\bstatus\b", normalized):
        response = status_review_message(
            fields,
            ("confirmed", "skipped", "unanswered"),
        )
    elif re.search(r"\b(?:make|made|invent|guess)\b", normalized):
        response = (
            "I did not invent those values. The confirmed answers came from "
            "information you provided and explicitly reviewed; nothing has "
            "changed."
        )
    elif re.search(
        r"\b(?:leave|keep).*(?:unchanged|as\s+it\s+is|confirmed)\b",
        normalized,
    ):
        response = (
            "Okay — I’ll keep the confirmed answers unchanged. Nothing on "
            "the form has changed."
        )
    elif re.search(
        r"\b(?:what\s+happens\s+next|what\s+should\s+i\s+do|next\s+step)\b",
        normalized,
    ):
        response = (
            "Next, review the completed PDF and any skipped fields, then "
            "download the form when it looks right."
        )
    elif re.search(r"\b(?:thank|thanks)\b", normalized):
        response = (
            "You’re welcome. The reviewed answers remain unchanged, and you "
            "can review the PDF or download it when you’re ready."
        )
    elif re.search(r"\b(?:repeat|again)\b", normalized):
        response = (
            "No more repetition is needed now. All supported questions have "
            "been reviewed, and the confirmed answers remain unchanged."
        )
    else:
        values = _confirmed_values_summary(confirmed_fields)
        status = (
            f"{len(confirmed_fields)} confirmed, {len(skipped_fields)} "
            f"skipped, and {len(unanswered_fields)} unanswered"
        )
        response = (
            f"The form has {status}. {values} Nothing on the form has changed."
        )

    return ConversationAction(
        action="conversation",
        message=truncate_text(response, 4000),
        field_id=None,
    )


def _confirmed_values_summary(fields: list[FormAgentField]) -> str:
    if not fields:
        return "There are no confirmed values to read back."
    visible = fields[:8]
    values = "; ".join(
        f"{field_display_name(field)} is "
        f"{format_agent_value(field.confirmed_value)}"
        for field in visible
    )
    if len(fields) > len(visible):
        values += f"; and {len(fields) - len(visible)} more"
    return f"Confirmed values: {values}."


def confirmed_action(
    field: FormAgentField,
    value: str | bool,
    fields: list[FormAgentField],
    *,
    replacement: bool = False,
    edited: bool = False,
) -> ConfirmedAction:
    question = truncate_text(field_question(field), 180).rstrip(" .?")
    next_field = _next_unanswered_field(fields, resolved_field_id=field.id)
    progression = progression_message(next_field)
    if replacement:
        acknowledgement = (
            "Thanks — I replaced the answer with your edited value"
            if edited
            else "Thanks — I replaced the answer with"
        )
    else:
        acknowledgement = (
            "Thanks — I added your edit"
            if edited
            else "Thanks — I added"
        )
    return ConfirmedAction(
        action="confirmed",
        message=(
            f'{acknowledgement} {format_agent_value(value)} for “{question}”. '
            f"{progression}"
        ),
        field_id=field.id,
        value=value,
    )


def build_field_clarification(field: FormAgentField) -> ClarifyAction:
    return adapter_clarification(field, clarification_for_field(field))


def adapter_clarification(
    field: FormAgentField,
    clarification: ClarificationNeeded,
) -> ClarifyAction:
    if clarification.reason.startswith(("Do you mean", "You said")):
        message = f"{clarification.reason} {clarification.accepted_shape}"
    else:
        question = truncate_text(field_question(field), 180).rstrip(" .?")
        message = (
            f'I want to make sure I get “{question}” right. '
            f"{clarification.reason} {clarification.accepted_shape}"
        )
    return ClarifyAction(
        action="clarify",
        message=message,
        field_id=field.id,
    )


def progress_action(
    request: FormAgentRequest,
    active_field: FormAgentField,
) -> ExplainAction:
    total = len(request.fields)
    confirmed = sum(field.status == "confirmed" for field in request.fields)
    skipped = sum(field.status == "skipped" for field in request.fields)
    proposed = int(request.conversation_state.pending_proposal is not None)
    unanswered = max(0, total - confirmed - skipped - proposed)
    question = truncate_text(field_question(active_field), 180).rstrip(" .?")

    parts = [f"You have confirmed {confirmed} of {total} supported questions"]
    if skipped:
        parts.append(f"skipped {skipped}")
    if proposed:
        parts.append("and have 1 answer awaiting confirmation")
    else:
        parts.append(f"and have {unanswered} unanswered")

    if proposed:
        recovery = (
            "You can review that proposal, ask me to explain the question, "
            "reject it, or skip it."
        )
    else:
        recovery = (
            "You can answer it, ask me to explain it, or skip it for now."
        )
    confirmed_fields = [
        field
        for field in request.fields
        if field.status == "confirmed" and field.confirmed_value is not None
    ][:3]
    confirmed_summary = ""
    if confirmed_fields:
        values = "; ".join(
            f'“{field_display_name(field)}” is '
            f"{format_agent_value(field.confirmed_value)}"
            for field in confirmed_fields
        )
        confirmed_summary = f" Confirmed so far: {values}."

    return ExplainAction(
        action="explain",
        message=(
            f"{', '.join(parts)}.{confirmed_summary} "
            f"We were working on “{question}”. "
            f"{recovery}"
        ),
        field_id=active_field.id,
    )


def skip_action(
    field: FormAgentField,
    fields: list[FormAgentField],
) -> SkipAction:
    question = truncate_text(field_question(field), 180).rstrip(" .?")
    next_field = _next_unanswered_field(fields, resolved_field_id=field.id)
    return SkipAction(
        action="skip",
        message=(
            f'No problem — I\'ll leave “{question}” unanswered for now. '
            f"{progression_message(next_field)}"
        ),
        field_id=field.id,
    )


def progression_message(next_field: Optional[FormAgentField]) -> str:
    if next_field is None:
        return "All supported fields have been reviewed."
    return f"Next, {build_next_field_question(next_field)}"


def format_agent_value(value: str | bool) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return f'"{value}"'
