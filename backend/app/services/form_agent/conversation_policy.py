from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from collections.abc import Callable
from typing import Literal, Optional

from pydantic import TypeAdapter

from .answer_preparation import (
    prepare_proposal_action,
    prose_polish_candidate,
)
from .answer_adapters import (
    AnswerAdapterResult,
    ClarificationNeeded,
    MatchedAnswer,
    clarification_for_field,
    interpret_answer,
    recover_prior_answer,
    remembered_answer,
)
from .models import (
    AdvanceEvent,
    CancelCorrectionEvent,
    ClarifyAction,
    ConfirmEditEvent,
    ConfirmEvent,
    ConfirmedAction,
    ConfirmedEffect,
    CompletedEffect,
    ConversationAction,
    ConversationPhase,
    ConversationState,
    ExplainAction,
    CorrectionCancelledAction,
    CorrectionCancelledEffect,
    CorrectionStartedAction,
    CorrectionStartedEffect,
    FieldReopenedAction,
    FieldReopenedEffect,
    FieldSelectedAction,
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
    RejectEvent,
    RejectedAction,
    RejectedEffect,
    ReplacementProposalEffect,
    ReplacementProposeAction,
    ReplacementRejectedAction,
    ReplacementRejectedEffect,
    SkipAction,
    SkippedEffect,
    SkipEvent,
    FieldSelectedEffect,
    WebGuidanceMetadata,
    field_question,
    request_active_field_id,
    request_message,
    truncate_text,
)
from .field_navigation import NavigationDecision, navigation_decision
from .value_normalizer import (
    canonicalize_field_value,
    validate_field_value,
)


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

TurnIntent = Literal[
    "command",
    "field_answer",
    "uncertain_answer",
    "wording_clarification",
    "evidence_question",
    "progress_question",
    "general_conversation",
    "prose_polish",
]
TurnObjective = Literal[
    "deterministic_command",
    "interpret_answer",
    "clarify_answer",
    "initial_paraphrase",
    "simplify_previous_explanation",
    "clarify_what_is_confusing",
    "evidence_grounded_explanation",
    "progress_help",
    "natural_conversation",
    "polish_prose",
]

ExplanationObjective = Literal[
    "initial_paraphrase",
    "simplify_previous_explanation",
    "clarify_what_is_confusing",
]


@dataclass(frozen=True)
class ExplanationRepairContext:
    objective: ExplanationObjective
    depth: int
    previous_explanation: Optional[str]

_PROGRESS_QUESTION_PATTERN = re.compile(
    r"\b(?:what|which)\s+(?:have\s+we|did\s+we|is)\s+"
    r"(?:complete|completed|done|left|remaining)\b|"
    r"\bhow\s+(?:far|much)\s+(?:are\s+we|have\s+we)\b|"
    r"\b(?:show|summari[sz]e|tell\s+me)\s+(?:my\s+|the\s+)?progress\b|"
    r"\b(?:form\s+)?progress\b|"
    r"\b(?:come|go|return)(?:\s+back)?\s+to\s+(?:this|it)"
    r"(?:\s+later)?\b|"
    r"\b(?:answer|do)\s+(?:this|it)\s+later\b",
    re.IGNORECASE,
)
_EXTERNAL_GUIDANCE_PATTERN = re.compile(
    r"\bwhy\b|"
    r"\b(?:what|which)\s+(?:is|was|are|were)\s+(?:the\s+)?"
    r"(?:purpose|reason)\b|"
    r"\b(?:purpose|reason)\s+(?:of|for)\b|"
    r"\b(?:is|are|was|were|am)\b.{0,80}\b(?:legally\s+required|"
    r"required|mandatory|optional|allowed|eligible)\b|"
    r"\bmust\s+(?:i|we|this|that|the)\b|"
    r"\b(?:legal\s+(?:effect|rules?|obligation)|law|eligibility\s+"
    r"requirements?|official\s+(?:instructions?|guidance|worksheet|form)|"
    r"current\s+guidance|check\s+(?:the\s+)?(?:web|guidance)|"
    r"search(?:\s+(?:the\s+)?web)?|sources?)\b|"
    r"\b(?:what|which|do|does|can|could)\b.{0,60}\binstructions?\b|"
    r"\bwhere\s+(?:can|could|do|would)\s+i\s+(?:find|locate|obtain|"
    r"look\s+up)\b",
    re.IGNORECASE,
)
_WORDING_CLARIFICATION_PATTERN = re.compile(
    r"\b(?:what\s+does\s+.{1,80}?\s+mean(?:\s+here)?|"
    r"what\s+does\s+(?:this|that|it|(?:this|that|the)\s+"
    r"(?:field|question))\s+mean|"
    r"what\s+is\s+(?:this|that|it|(?:this|that|the)\s+"
    r"(?:field|question))\s+asking|"
    r"explain(?:\s+(?:this|that|it|the\s+(?:field|question)))?|"
    r"clarify(?:\s+(?:this|that|it|the\s+(?:field|question)))?|"
    r"rephrase(?:\s+(?:this|that|it|the\s+(?:field|question)))?|"
    r"plain\s+(?:english|language)|more\s+simply|simpler\s+words?|"
    r"what\s+should\s+i\s+(?:put|enter|write|answer|choose)|"
    r"what\s+(?:this|that|the)\s+(?:box|field)\s+wants?\s+me\s+to\s+say|"
    r"what\s+do\s+you\s+need\s+me\s+to\s+say|"
    r"ask\s+(?:me\s+)?(?:that|this|it)\s+(?:normally|simply)|"
    r"ask\s+the\s+question\s+in\s+(?:one\s+)?simple\s+sentence)\b",
    re.IGNORECASE,
)
_CONVERSATION_REPAIR_PATTERN = re.compile(
    r"\b(?:again|another\s+way|more\s+simply|simpler\s+words?|"
    r"still\s+(?:do\s+not|don't|cannot|can't)\s+understand|"
    r"(?:i\s+)?(?:do\s+not|don't|cannot|can't)\s+understand|"
    r"still\s+confused|confusing|does(?:\s+not|n't)\s+make\s+sense)\b",
    re.IGNORECASE,
)
_UNCERTAIN_ANSWER_PATTERN = re.compile(
    r"\b(?:about|approximately|around|roughly|maybe|perhaps|not\s+sure|"
    r"unsure|i\s+think|probably|possibly|sometime|between)\b",
    re.IGNORECASE,
)
_UNRELATED_WORKFLOW_PATTERN = re.compile(
    r"\b(?:first|next)\s+unanswered\s+field\b|"
    r"\bthis\s+is\s+(?:the\s+)?(?:first|next)\s+(?:field|question)\b|"
    r"\byou\s+have\s+confirmed\s+\d+\b|"
    r"\bform\s+progress\b",
    re.IGNORECASE,
)
_GENERAL_CONVERSATION_PATTERN = re.compile(
    r"^(?:hi|hello|hey|thanks|thank\s+you|okay(?:,?\s+that\s+makes\s+"
    r"sense)?|okay\s+thanks|got\s+it|i\s+understand)[.!]?$|"
    r"\b(?:i\s+(?:am|'m)\s+(?:confused|nervous|worried|overwhelmed)|"
    r"help\s+me\s+(?:with|through)\s+(?:this|the)\s+form|"
    r"can\s+we\s+pause|let(?:'s|\s+us)\s+pause|"
    r"(?:go|speak|take\s+it)\s+slow(?:ly)?|keep\s+it\s+simple|"
    r"this\s+wording\s+is\s+(?:exhausting|frustrating|confusing))\b",
    re.IGNORECASE,
)

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

_REPEATED_EXPLANATION_ERROR = (
    "Form Agent repeated the previous explanation"
)
_UNRELATED_WORKFLOW_ERROR = (
    "Form Agent added unrelated workflow commentary to an explanation"
)
_LOST_ACTIVE_FIELD_ERROR = "Form Agent lost the active field context"
_UNSUPPORTED_FORMAT_CLAIM_ERROR = (
    "Form Agent claimed a format that is absent from the field context"
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


def classify_turn_intent(request: FormAgentRequest) -> TurnIntent:
    if not isinstance(request.event, (MessageEvent, FocusFieldEvent)):
        return "command"

    active_field_id = request_active_field_id(request)
    if active_field_id is not None:
        active_field = next(
            (field for field in request.fields if field.id == active_field_id),
            None,
        )
        if (
            active_field is not None
            and prose_polish_candidate(
                active_field,
                request_message(request),
            )
            is not None
        ):
            return "prose_polish"

    return _classify_message(request_message(request))


def _classify_message(message: str) -> TurnIntent:
    message = message.strip()
    if _PROGRESS_QUESTION_PATTERN.search(message) is not None:
        return "progress_question"
    if _EXTERNAL_GUIDANCE_PATTERN.search(message) is not None:
        return "evidence_question"
    if (
        _WORDING_CLARIFICATION_PATTERN.search(message) is not None
        or _CONVERSATION_REPAIR_PATTERN.search(message) is not None
    ):
        return "wording_clarification"
    if _UNCERTAIN_ANSWER_PATTERN.search(message) is not None:
        return "uncertain_answer"
    if message.endswith("?") or _GENERAL_CONVERSATION_PATTERN.search(message):
        return "general_conversation"
    return "field_answer"


def turn_objective(request: FormAgentRequest) -> TurnObjective:
    intent = classify_turn_intent(request)
    if intent == "wording_clarification":
        return explanation_repair_context(request).objective
    return {
        "command": "deterministic_command",
        "field_answer": "interpret_answer",
        "uncertain_answer": "clarify_answer",
        "evidence_question": "evidence_grounded_explanation",
        "progress_question": "progress_help",
        "general_conversation": "natural_conversation",
        "prose_polish": "polish_prose",
    }[intent]


def explanation_repair_context(
    request: FormAgentRequest,
) -> ExplanationRepairContext:
    explanations: list[str] = []
    awaiting_explanation = False

    for message in request.history:
        if message.role == "user":
            awaiting_explanation = (
                _classify_message(message.content) == "wording_clarification"
            )
            continue
        if awaiting_explanation:
            explanations.append(message.content.strip())
        awaiting_explanation = False

    if (
        not explanations
        and request.conversation_state.phase == "awaiting_clarification"
        and _CONVERSATION_REPAIR_PATTERN.search(request_message(request))
        is not None
    ):
        previous_assistant_message = next(
            (
                message.content.strip()
                for message in reversed(request.history)
                if message.role == "assistant"
            ),
            None,
        )
        if previous_assistant_message:
            explanations.append(previous_assistant_message)

    depth = min(3, len(explanations) + 1)
    objective: ExplanationObjective = {
        1: "initial_paraphrase",
        2: "simplify_previous_explanation",
        3: "clarify_what_is_confusing",
    }[depth]
    return ExplanationRepairContext(
        objective=objective,
        depth=depth,
        previous_explanation=(explanations[-1] if explanations else None),
    )


def explanations_are_near_duplicate(first: str, second: str) -> bool:
    first_words = _comparison_words(first)
    second_words = _comparison_words(second)
    if not first_words or not second_words:
        return False

    first_text = " ".join(first_words)
    second_text = " ".join(second_words)
    if first_text == second_text:
        return True

    sequence_similarity = SequenceMatcher(
        None,
        first_text,
        second_text,
    ).ratio()
    first_tokens = set(first_words)
    second_tokens = set(second_words)
    shared_tokens = first_tokens & second_tokens
    union_tokens = first_tokens | second_tokens
    token_similarity = len(shared_tokens) / len(union_tokens)
    containment = len(shared_tokens) / min(
        len(first_tokens),
        len(second_tokens),
    )
    return sequence_similarity >= 0.82 or (
        token_similarity >= 0.72 and containment >= 0.88
    )


def explanation_repair_fallback(
    error: FormAgentError,
    request: FormAgentRequest,
) -> Optional[ExplainAction]:
    if str(error) not in {
        _REPEATED_EXPLANATION_ERROR,
        _UNRELATED_WORKFLOW_ERROR,
        _LOST_ACTIVE_FIELD_ERROR,
        _UNSUPPORTED_FORMAT_CLAIM_ERROR,
    }:
        return None
    if classify_turn_intent(request) != "wording_clarification":
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

    intent = classify_turn_intent(request)
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


def _comparison_words(value: str) -> list[str]:
    return re.findall(r"[\w']+", value.casefold(), re.UNICODE)


def message_needs_external_guidance(request: FormAgentRequest) -> bool:
    return classify_turn_intent(request) == "evidence_question"


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
        raise FormAgentTransitionError(
            "The form-complete state is stale"
        )

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


def validate_action_for_turn(
    action: FormAgentAction,
    request: FormAgentRequest,
    guidance: tuple[OfficialGuidanceCitation, ...] = (),
) -> None:
    intent = classify_turn_intent(request)
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
        raise FormAgentError(_REPEATED_EXPLANATION_ERROR)
    if _UNRELATED_WORKFLOW_PATTERN.search(action.message) is not None:
        raise FormAgentError(_UNRELATED_WORKFLOW_ERROR)
    if not _response_mentions_active_field(action.message, request):
        raise FormAgentError(_LOST_ACTIVE_FIELD_ERROR)


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
        raise FormAgentError(_UNSUPPORTED_FORMAT_CLAIM_ERROR)
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
        raise FormAgentError(_UNSUPPORTED_FORMAT_CLAIM_ERROR)


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
        and classify_turn_intent(request) == "wording_clarification"
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


def _active_field_return_anchor(field: FormAgentField) -> str:
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
    return truncate_text(_field_display_name(field).casefold(), 80)


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


def _active_field_side_question_action(
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
    question = _field_display_name(field)
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
    if re.search(r"\b(?:occupancy|commenced|started\s+living|move.?in)\b", metadata):
        return "When did you start living at your current home?"
    if "preferred" in metadata or "name you want" in metadata:
        return "What name would you like us to use?"
    if re.search(r"\b(?:what happened|help you need|already tried)\b", metadata):
        return (
            "What happened, what help do you need, and what have you already "
            "tried?"
        )
    return build_next_field_question(field)


def _navigation_action(
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
        return _correction_cancelled_action(field, request.fields)

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
            return _progress_action(request, active_field)
        return ConversationAction(
            action="conversation",
            message=_status_review_message(request.fields, decision.statuses),
            field_id=active_field_id,
        )

    if decision.kind == "review_value":
        if len(decision.matches) == 1:
            field = decision.matches[0]
            return ConversationAction(
                action="conversation",
                message=(
                    f'Your confirmed answer for “{_field_display_name(field)}” '
                    f"is {format_agent_value(field.confirmed_value)}. Nothing "
                    "on the form has changed."
                ),
                field_id=active_field_id,
            )
        return ConversationAction(
            action="conversation",
            message=_field_match_clarification(
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
            message=_field_match_clarification(
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
                f'I reopened “{_field_display_name(field)}”. '
                f"{build_next_field_question(field)}"
            ),
            field_id=field.id,
        )
    if decision.kind == "correct":
        return CorrectionStartedAction(
            action="correction_started",
            message=(
                f'Your current confirmed answer for “{_field_display_name(field)}” '
                f"is {format_agent_value(field.confirmed_value)}. It will stay "
                "on the form unless you explicitly confirm a replacement. "
                "What should the replacement be?"
            ),
            field_id=field.id,
        )
    return None


def _correction_cancelled_action(
    field: FormAgentField,
    fields: list[FormAgentField],
) -> CorrectionCancelledAction:
    next_field = _next_unanswered_field(fields)
    return CorrectionCancelledAction(
        action="correction_cancelled",
        message=(
            f'Correction cancelled. Your confirmed answer for '
            f'“{_field_display_name(field)}” remains '
            f"{format_agent_value(field.confirmed_value)}. "
            f"{_progression_message(next_field)}"
        ),
        field_id=field.id,
    )


def _status_review_message(
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
                f"{_field_display_name(field)} is "
                f"{format_agent_value(field.confirmed_value)}"
                if status == "confirmed"
                else _field_display_name(field)
            )
            for field in visible
        )
        if len(matching) > len(visible):
            names += f"; and {len(matching) - len(visible)} more"
        sections.append(
            f"{labels[status]} ({len(matching)}): {names or 'none'}"
        )
    return ". ".join(sections) + ". Nothing on the form has changed."


def _field_match_clarification(
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
    options = "; ".join(_field_display_name(field) for field in visible)
    remainder = (
        f"; and {len(matches) - len(visible)} more"
        if len(matches) > len(visible)
        else ""
    )
    return (
        f"I found more than one matching {required_kind}: {options}{remainder}. "
        "Which one did you mean? Nothing on the form has changed."
    )


def _field_display_name(field: FormAgentField) -> str:
    return truncate_text(field_question(field), 180).rstrip(" .?")


def _next_unanswered_action(fields: list[FormAgentField]) -> NextAction:
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


def _start_conversation_action(fields: list[FormAgentField]) -> NextAction:
    action = _next_unanswered_action(fields)
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


def _completed_conversation_action(
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
        response = _status_review_message(fields, ("skipped",))
    elif re.search(r"\b(?:unanswered|remaining|left)\b", normalized):
        response = _status_review_message(fields, ("unanswered",))
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
                f" for {_field_display_name(longest)}: "
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
        response = _status_review_message(
            fields,
            ("confirmed", "skipped", "unanswered"),
        )
    elif re.search(r"\b(?:make|made|invent|guess)\b", normalized):
        response = (
            "I did not invent those values. The confirmed answers came from "
            "information you provided and explicitly reviewed; nothing has "
            "changed."
        )
    elif re.search(r"\b(?:leave|keep).*(?:unchanged|as\s+it\s+is|confirmed)\b", normalized):
        response = (
            "Okay — I’ll keep the confirmed answers unchanged. Nothing on "
            "the form has changed."
        )
    elif re.search(r"\b(?:what\s+happens\s+next|what\s+should\s+i\s+do|next\s+step)\b", normalized):
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
        f"{_field_display_name(field)} is "
        f"{format_agent_value(field.confirmed_value)}"
        for field in visible
    )
    if len(fields) > len(visible):
        values += f"; and {len(fields) - len(visible)} more"
    return f"Confirmed values: {values}."


def _confirmed_action(
    field: FormAgentField,
    value: str | bool,
    fields: list[FormAgentField],
    *,
    replacement: bool = False,
    edited: bool = False,
) -> ConfirmedAction:
    question = truncate_text(field_question(field), 180).rstrip(" .?")
    next_field = _next_unanswered_field(fields, resolved_field_id=field.id)
    progression = _progression_message(next_field)
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


def _build_field_clarification(field: FormAgentField) -> ClarifyAction:
    return _adapter_clarification(field, clarification_for_field(field))


def _adapter_clarification(
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


def _progress_action(
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
            f'“{_field_display_name(field)}” is '
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


def _skip_action(
    field: FormAgentField,
    fields: list[FormAgentField],
) -> SkipAction:
    question = truncate_text(field_question(field), 180).rstrip(" .?")
    next_field = _next_unanswered_field(fields, resolved_field_id=field.id)
    return SkipAction(
        action="skip",
        message=(
            f'No problem — I\'ll leave “{question}” unanswered for now. '
            f"{_progression_message(next_field)}"
        ),
        field_id=field.id,
    )


def _state_after_resolution(
    resolved_field_id: str,
    fields: list[FormAgentField],
    *,
    remembered_candidates: list[RememberedCandidate],
) -> ConversationState:
    next_field = _next_unanswered_field(
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
    next_field = _next_unanswered_field(fields)
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


def _next_unanswered_field(
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


def _progression_message(next_field: Optional[FormAgentField]) -> str:
    if next_field is None:
        return "All supported fields have been reviewed."
    return f"Next, {build_next_field_question(next_field)}"


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
            {"address", "home", "housing", "live", "living", "move", "own", "rent", "stay"}
        )
    if re.search(r"\b(?:date|day|month|year|when)\b", metadata):
        anchors.update({"date", "day", "month", "year", "when"})
    if re.search(r"\b(?:income|earn|money|salary|wage)\b", metadata):
        anchors.update({"earn", "income", "money", "month", "monthly", "pay"})
    response_words = set(_comparison_words(message))
    return bool(anchors & response_words)
