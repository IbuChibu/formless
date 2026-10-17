"""Stable public policy surface for the Form Agent conversation workflow.

The implementation is split by responsibility so callers do not need to know
which internal module owns intent, state, action, or response policy.
"""

from .conversation_actions import (
    conflicting_guidance_action,
    deterministic_action,
    explanation_repair_fallback,
    insufficient_guidance_action,
    invalid_value_clarification,
    model_failure_fallback,
    normalize_action_message,
    unexpected_navigation_clarification,
)
from .action_validation import validate_action_for_turn
from .intent_policy import (
    ExplanationObjective,
    ExplanationRepairContext,
    TurnIntent,
    TurnObjective,
    classify_turn_intent,
    explanation_repair_context,
    explanations_are_near_duplicate,
    message_needs_external_guidance,
    turn_objective,
)
from .navigation_policy import build_next_field_question, format_agent_value
from .state_machine import response_for_action, validate_event_transition

__all__ = [
    "ExplanationObjective",
    "ExplanationRepairContext",
    "TurnIntent",
    "TurnObjective",
    "build_next_field_question",
    "classify_turn_intent",
    "conflicting_guidance_action",
    "deterministic_action",
    "explanation_repair_context",
    "explanation_repair_fallback",
    "explanations_are_near_duplicate",
    "format_agent_value",
    "insufficient_guidance_action",
    "invalid_value_clarification",
    "message_needs_external_guidance",
    "model_failure_fallback",
    "normalize_action_message",
    "response_for_action",
    "turn_objective",
    "unexpected_navigation_clarification",
    "validate_action_for_turn",
    "validate_event_transition",
]
