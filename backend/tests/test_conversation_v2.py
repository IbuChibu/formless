from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi.testclient import TestClient

from app.main import app, get_conversation_v2_service
from app.services.conversation_v2 import ConversationV2Service
from app.services.form_agent import FormAgentError, FormAgentRequest


class StubNemotron:
    def __init__(self, response: dict[str, Any] | list[dict[str, Any]]) -> None:
        self.responses = response if isinstance(response, list) else [response]
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return json.dumps(response)


def field(
    field_id: str,
    label: str,
    *,
    field_type: str = "text",
    options: list[str] | None = None,
    status: str = "unanswered",
    confirmed_value: str | bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": field_id,
        "label": label,
        "question": label,
        "type": field_type,
        "status": status,
    }
    if options is not None:
        result["options"] = options
    if confirmed_value is not None:
        result["confirmed_value"] = confirmed_value
    return result


def request(
    message: str,
    *,
    fields: list[dict[str, Any]] | None = None,
    active_field_id: str | None = "full_name",
    phase: str = "awaiting_answer",
    pending: dict[str, Any] | None = None,
    support_setup_step: str | None = None,
) -> FormAgentRequest:
    conversation_state: dict[str, Any] = {
        "phase": phase,
        "active_field_id": active_field_id,
        "pending_proposal": pending,
    }
    if support_setup_step is not None:
        conversation_state["support_setup_step"] = support_setup_step
    return FormAgentRequest.model_validate(
        {
            "form_context": {"title": "Synthetic form"},
            "fields": fields or [field("full_name", "Full legal name")],
            "conversation_state": conversation_state,
            "event": {"type": "message", "content": message},
            "assistance_preferences": {
                "support_needs": ["plain_language"],
                "interaction_mode": "voice",
                "assistance_language": "en",
            },
            "history": [
                {"role": "assistant", "content": "What should I enter?"},
                {"role": "user", "content": message},
            ],
        }
    )


def respond(
    model_response: dict[str, Any] | list[dict[str, Any]],
    agent_request: FormAgentRequest,
):
    model = StubNemotron(model_response)
    response = asyncio.run(
        ConversationV2Service(model).respond(agent_request)  # type: ignore[arg-type]
    )
    return response, model


def test_explanation_is_model_led_and_does_not_mutate_state() -> None:
    response, model = respond(
        {
            "reply": "Occupancy means living somewhere. This asks when you moved into your current home.",
            "effect": {"type": "none", "awaiting": "clarification"},
        },
        request("What does occupancy mean?"),
    )

    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "awaiting_clarification"
    assert "What does occupancy mean?" in model.calls[0]["user_prompt"]
    assert model.calls[0]["json_response"] is True


def test_explanation_keeps_the_existing_answer_phase() -> None:
    response, _ = respond(
        {
            "reply": "A legal name is the name shown on official documents.",
            "effect": {"type": "none", "awaiting": "answer"},
        },
        request("What does legal name mean?"),
    )

    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "awaiting_answer"


def test_alternative_date_can_be_explained_without_a_proposal() -> None:
    response, _ = respond(
        {
            "reply": "Did you mean 17 November 2011?",
            "effect": {"type": "none", "awaiting": "clarification"},
        },
        request("11/17/2011"),
    )

    assert response.assistant_message == "Did you mean 17 November 2011?"
    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "awaiting_clarification"


def test_exact_dropdown_proposal_is_unconfirmed() -> None:
    fields = [
        field(
            "tenure",
            "Housing arrangement",
            field_type="dropdown",
            options=["Sole tenant", "Joint tenant", "Owner-occupier"],
        )
    ]
    response, _ = respond(
        {
            "reply": "‘Solo tenant’ matches the available option ‘Sole tenant’. Is that right?",
            "effect": {
                "type": "propose_value",
                "field_id": "tenure",
                "value": "Sole tenant",
                "heard_value": "Solo tenant",
            },
        },
        request("Solo tenant", fields=fields, active_field_id="tenure"),
    )

    assert response.effect.effect == "proposal"
    assert response.effect.prepared_value == "Sole tenant"
    assert response.conversation_state.phase == "awaiting_confirmation"


def test_transformed_dropdown_requires_a_transparent_mapping() -> None:
    fields = [
        field(
            "tenure",
            "Housing arrangement",
            field_type="dropdown",
            options=["Sole tenant", "Joint tenant", "Owner-occupier"],
        )
    ]
    response, model = respond(
        [
            {
                "reply": "Sole tenant — is that right?",
                "effect": {
                    "type": "propose_value",
                    "field_id": "tenure",
                    "value": "Sole tenant",
                    "heard_value": "Solo tenant",
                },
            },
            {
                "reply": "‘Solo tenant’ matches the available option ‘Sole tenant’. Is that right?",
                "effect": {
                    "type": "propose_value",
                    "field_id": "tenure",
                    "value": "Sole tenant",
                    "heard_value": "Solo tenant",
                },
            },
        ],
        request("Solo tenant", fields=fields, active_field_id="tenure"),
    )

    assert response.effect.effect == "proposal"
    assert response.effect.prepared_value == "Sole tenant"
    assert len(model.calls) == 2


def test_normalized_proposal_reads_back_the_exact_stored_value() -> None:
    response, model = respond(
        [
            {
                "reply": "19 May 2011 — is that right?",
                "effect": {
                    "type": "propose_value",
                    "field_id": "date_of_birth",
                    "value": "19/05/2011",
                    "heard_value": "the nineteenth of May 2011",
                },
            },
            {
                "reply": "I’ll use 19/05/2011 — is that right?",
                "effect": {
                    "type": "propose_value",
                    "field_id": "date_of_birth",
                    "value": "19/05/2011",
                    "heard_value": "the nineteenth of May 2011",
                },
            },
        ],
        request(
            "The nineteenth of May 2011",
            fields=[field("date_of_birth", "Date of birth (DD/MM/YYYY)")],
            active_field_id="date_of_birth",
        ),
    )

    assert response.effect.effect == "proposal"
    assert response.effect.prepared_value == "19/05/2011"
    assert "19/05/2011" in response.assistant_message
    assert len(model.calls) == 2


def test_invented_dropdown_option_is_rejected() -> None:
    fields = [
        field(
            "tenure",
            "Housing arrangement",
            field_type="dropdown",
            options=["Sole tenant", "Joint tenant"],
        )
    ]
    response, _ = respond(
        [
            {
                "reply": "I will use Living alone.",
                "effect": {
                    "type": "propose_value",
                    "field_id": "tenure",
                    "value": "Living alone",
                },
            },
            {
                "reply": "Living alone does not tell me whether you rent or own.",
                "effect": {
                    "type": "propose_value",
                    "field_id": "tenure",
                    "value": "Living alone",
                },
            },
        ],
        request("I live by myself", fields=fields, active_field_id="tenure"),
    )

    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "awaiting_clarification"


def test_natural_confirmation_applies_only_the_pending_value() -> None:
    response, _ = respond(
        {"reply": "Thanks — I’ve added that.", "effect": {"type": "confirm_proposal"}},
        request(
            "Confirm",
            phase="awaiting_confirmation",
            pending={"field_id": "full_name", "value": "John Michael"},
        ),
    )

    assert response.effect.model_dump() == {
        "effect": "confirmed",
        "field_id": "full_name",
        "value": "John Michael",
    }


def test_clear_spoken_confirmations_resolve_without_a_model_retry() -> None:
    fields = [
        field("full_name", "Full legal name"),
        field("preferred_name", "Preferred name"),
    ]
    for phrase in ("Yeah.", "Yes.", "Correct.", "Confirm. Confirm."):
        response, model = respond(
            {"reply": "This model response must not be used.", "effect": {"type": "none"}},
            request(
                phrase,
                fields=fields,
                phase="awaiting_confirmation",
                pending={"field_id": "full_name", "value": "Ebrahim Akhoon"},
            ),
        )

        assert response.effect.model_dump() == {
            "effect": "confirmed",
            "field_id": "full_name",
            "value": "Ebrahim Akhoon",
        }
        assert response.conversation_state.phase == "awaiting_answer"
        assert response.conversation_state.active_field_id == "preferred_name"
        assert "Preferred name" in response.assistant_message
        assert model.calls == []


def test_qualified_yes_still_uses_semantic_interpretation() -> None:
    response, model = respond(
        {
            "reply": "No problem — what should I use instead?",
            "effect": {"type": "reject_proposal"},
        },
        request(
            "Yes, but change the spelling.",
            phase="awaiting_confirmation",
            pending={"field_id": "full_name", "value": "Ebrahim Akhoon"},
        ),
    )

    assert response.effect.effect == "rejected"
    assert len(model.calls) == 1


def test_spoken_confirmation_reads_back_a_checkbox_naturally() -> None:
    response, model = respond(
        {"reply": "This model response must not be used.", "effect": {"type": "none"}},
        request(
            "Yes.",
            fields=[field("accept_terms", "Accept terms", field_type="checkbox")],
            active_field_id="accept_terms",
            phase="awaiting_confirmation",
            pending={"field_id": "accept_terms", "value": True},
        ),
    )

    assert response.effect.value is True
    assert '"Yes"' in response.assistant_message
    assert model.calls == []


def test_near_match_cannot_confirm_even_if_model_requests_it() -> None:
    response, _ = respond(
        [
            {
                "reply": "Thanks, that is confirmed.",
                "effect": {"type": "confirm_proposal"},
            },
            {
                "reply": "I still need you to confirm, change, reject, or repeat it.",
                "effect": {"type": "confirm_proposal"},
            },
        ],
        request(
            "Permit.",
            phase="awaiting_confirmation",
            pending={"field_id": "full_name", "value": "Ebrahim Akhoon"},
        ),
    )

    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "awaiting_confirmation"
    assert response.conversation_state.pending_proposal is not None


def test_input_mode_request_updates_preferences_not_form_data() -> None:
    response, _ = respond(
        {
            "reply": "Of course — you can type your answer.",
            "effect": {"type": "change_input_mode", "mode": "typing"},
        },
        request("Let me type instead"),
    )

    assert response.effect.effect == "assistance_preferences_updated"
    assert response.effect.preferences.interaction_mode == "typing"
    assert response.conversation_state.active_field_id == "full_name"


def test_natural_support_request_updates_bounded_preferences() -> None:
    response, _ = respond(
        {
            "reply": "Of course — I’ll use simpler words and take it slowly.",
            "effect": {
                "type": "update_assistance",
                "support_needs": ["plain_language", "slower_pace"],
            },
        },
        request("Could you use simpler words and go slowly?"),
    )

    assert response.effect.effect == "assistance_preferences_updated"
    assert response.effect.preferences.support_needs == [
        "plain_language",
        "slower_pace",
    ]


def test_support_introduction_stays_open_until_input_preference() -> None:
    response, _ = respond(
        {
            "reply": "Of course. Would you rather speak, type, or use either?",
            "effect": {
                "type": "update_assistance",
                "support_needs": ["plain_language"],
            },
        },
        request(
            "Use simpler words",
            phase="support_setup",
            active_field_id=None,
            support_setup_step="needs",
        ),
    )

    assert response.conversation_state.phase == "support_setup"
    assert response.conversation_state.support_setup_step == "interaction"


def test_v2_endpoint_uses_separate_service() -> None:
    service = ConversationV2Service(  # type: ignore[arg-type]
        StubNemotron(
            {"reply": "What part should I explain?", "effect": {"type": "none"}}
        )
    )
    app.dependency_overrides[get_conversation_v2_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/agent/v2/respond",
            json=request("What does this mean?").model_dump(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["assistant_message"] == "What part should I explain?"


def test_non_mutating_decision_gets_one_model_led_effect_audit() -> None:
    response, model = respond(
        [
            {
                "reply": "I have recorded Jordan Lee.",
                "effect": {"type": "none"},
            },
            {
                "reply": "Jordan Lee — is that exactly right?",
                "effect": {
                    "type": "propose_value",
                    "field_id": "full_name",
                    "value": "Jordan Lee",
                    "heard_value": "Jordan Lee",
                },
            },
        ],
        request("Jordan Lee"),
    )

    assert response.effect.effect == "proposal"
    assert len(model.calls) == 2
    assert "Audit only whether the effect matches" in model.calls[1]["user_prompt"]


def test_model_can_propose_for_a_clearly_referenced_unanswered_field() -> None:
    fields = [
        field("preferred_name", "Preferred name"),
        field("household_count", "Household count", field_type="number"),
    ]
    response, _ = respond(
        {
            "reply": "1 person, including you — is that right?",
            "effect": {
                "type": "propose_value",
                "field_id": "household_count",
                "value": "1",
                "heard_value": "one, just me",
            },
        },
        request(
            "It should be one, just me",
            fields=fields,
            active_field_id="preferred_name",
        ),
    )

    assert response.effect.effect == "proposal"
    assert response.effect.field_id == "household_count"
    assert response.conversation_state.active_field_id == "household_count"
