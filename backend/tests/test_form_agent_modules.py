from __future__ import annotations

import pytest

from app.services.form_agent import (
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    NextAction,
    ProposeAction,
)
from app.services.form_agent.conversation_policy import deterministic_action
from app.services.form_agent.prompt_builder import (
    MAX_AGENT_CONTEXT_CHARS,
    build_agent_context,
    build_user_prompt,
)
from app.services.form_agent.response_parser import (
    canonicalize_proposal_value,
    parse_action,
    validate_action_against_request,
)
from app.services.form_agent.value_normalizer import (
    canonicalize_field_value,
    infer_unambiguous_answer,
)


def _request(*, active_field_id: str | None = "arrangement") -> FormAgentRequest:
    return FormAgentRequest(
        fields=[
            FormAgentField(
                id="full_name",
                label="Full name",
                type="text",
            ),
            FormAgentField(
                id="arrangement",
                label="Living arrangement",
                question="Which option best describes where you live?",
                type="dropdown",
                options=["Rent", "Own"],
            ),
        ],
        active_field_id=active_field_id,
        message="Here is my answer.",
    )


def test_conversation_policy_selects_the_first_unanswered_field() -> None:
    action = deterministic_action(_request(active_field_id=None))

    assert isinstance(action, NextAction)
    assert action.field_id == "full_name"
    assert action.message == "Full name. What should be entered here?"


def test_prompt_builder_returns_bounded_structured_untrusted_context() -> None:
    request = _request()

    context = build_agent_context(request)
    prompt = build_user_prompt(request)

    assert context["active_field"]["id"] == "arrangement"  # type: ignore[index]
    assert context["ordered_questions"][0]["id"] == "full_name"  # type: ignore[index]
    assert len(str(context)) < MAX_AGENT_CONTEXT_CHARS
    assert prompt.startswith("UNTRUSTED_AGENT_CONTEXT\n")
    assert prompt.endswith(
        "Choose exactly one allowed action. Do not confirm or apply values."
    )


def test_response_parser_canonicalizes_and_validates_a_proposal() -> None:
    request = _request()
    parsed = parse_action(
        '{"action":"propose","message":"Proposal",'
        '"field_id":"arrangement","value":"rent"}'
    )

    action = canonicalize_proposal_value(parsed, request)
    validate_action_against_request(action, request)

    assert isinstance(action, ProposeAction)
    assert action.value == "Rent"


def test_response_parser_rejects_an_unknown_field() -> None:
    action = parse_action(
        '{"action":"explain","message":"Explanation",'
        '"field_id":"unknown"}'
    )

    with pytest.raises(FormAgentError, match="unknown field ID"):
        validate_action_against_request(action, _request())


def test_value_normalizer_is_independent_of_agent_orchestration() -> None:
    assert canonicalize_field_value("number", None, "£1,250.00") == "1250.00"
    assert infer_unambiguous_answer(
        "dropdown",
        ["Rent", "Own"],
        "I rent my home.",
    ) == "Rent"
    assert infer_unambiguous_answer(
        "dropdown",
        ["Rent", "Own"],
        "What does Rent mean?",
    ) is None
