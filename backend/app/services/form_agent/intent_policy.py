"""Classify a user turn and track bounded explanation-repair intent."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Literal, Optional

from .answer_preparation import prose_polish_candidate
from .models import (
    FocusFieldEvent,
    FormAgentRequest,
    MessageEvent,
    request_active_field_id,
    request_message,
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


def _comparison_words(value: str) -> list[str]:
    return re.findall(r"[\w']+", value.casefold(), re.UNICODE)


def message_needs_external_guidance(request: FormAgentRequest) -> bool:
    return classify_turn_intent(request) == "evidence_question"
