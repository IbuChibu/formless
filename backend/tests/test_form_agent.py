from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_form_agent_service
from app.services.form_agent_service import (
    FormAgentError,
    FormAgentRequest,
    FormAgentService,
)
from app.services.nemotron_service import NemotronServiceError


client = TestClient(app)


class StubNemotronService:
    def __init__(
        self,
        response: str | list[str] = "",
        error: NemotronServiceError | None = None,
    ) -> None:
        self.responses = (
            response.copy() if isinstance(response, list) else [response]
        )
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 600,
        json_response: bool = False,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "max_tokens": max_tokens,
                "json_response": json_response,
            }
        )
        if self.error is not None:
            raise self.error
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def agent_request_payload() -> dict[str, Any]:
    return {
        "fields": [
            {
                "id": "full_name",
                "label": "Full name",
                "type": "text",
                "status": "unanswered",
            },
            {
                "id": "living_arrangement",
                "label": "Which option best describes where you live?",
                "type": "dropdown",
                "options": ["Rent", "Own", "Staying with someone"],
                "status": "unanswered",
            },
            {
                "id": "shares_costs",
                "label": "Do you share household costs?",
                "type": "checkbox",
                "status": "confirmed",
                "confirmed_value": False,
            },
        ],
        "active_field_id": "living_arrangement",
        "message": "I rent my home.",
        "history": [
            {
                "role": "assistant",
                "content": "Which option describes where you live?",
            },
            {"role": "user", "content": "I rent my home."},
        ],
    }


def post_with_nemotron(
    nemotron_service: StubNemotronService,
    payload: dict[str, Any],
):
    agent_service = FormAgentService(nemotron_service)  # type: ignore[arg-type]
    app.dependency_overrides[get_form_agent_service] = lambda: agent_service
    try:
        return client.post("/agent/respond", json=payload)
    finally:
        app.dependency_overrides.clear()


def test_agent_returns_a_validated_proposal_without_confirming_it() -> None:
    nemotron = StubNemotronService(
        '{"action":"propose","message":"You said you rent. '
        'Would you like to use Rent?","field_id":"living_arrangement",'
        '"value":"Rent"}'
    )
    request = FormAgentRequest.model_validate(agent_request_payload())

    action = asyncio.run(
        FormAgentService(nemotron).respond(request)  # type: ignore[arg-type]
    )

    assert action.model_dump() == {
        "action": "propose",
        "message": (
            'I understood your answer as "Rent". This proposal is awaiting '
            "your confirmation and has not been applied to the form."
        ),
        "field_id": "living_arrangement",
        "value": "Rent",
    }
    assert request.fields[1].status == "unanswered"
    assert request.fields[1].confirmed_value is None
    assert len(nemotron.calls) == 1
    call = nemotron.calls[0]
    assert call["max_tokens"] == 600
    assert call["json_response"] is True
    assert "Never invent personal facts" in call["system_prompt"]
    assert "Never invent why a form owner asks" in call["system_prompt"]
    assert "only form-wide context" in call["system_prompt"]
    assert "untrusted data" in call["system_prompt"]
    assert '"confirmed_value": false' in call["user_prompt"]
    assert '"active_field_id": "living_arrangement"' in call["user_prompt"]


def test_agent_retries_one_invalid_proposal_schema() -> None:
    nemotron = StubNemotronService(
        [
            '{"action":"propose","message":"You rent.",'
            '"field_id":"living_arrangement"}',
            '{"action":"propose","message":"You rent.",'
            '"field_id":"living_arrangement","value":"Rent"}',
        ]
    )
    request = FormAgentRequest.model_validate(agent_request_payload())

    action = asyncio.run(
        FormAgentService(nemotron).respond(request)  # type: ignore[arg-type]
    )

    assert action.action == "propose"
    assert action.value == "Rent"
    assert "awaiting your confirmation" in action.message
    assert len(nemotron.calls) == 2
    assert "previous response failed" in nemotron.calls[1][
        "system_prompt"
    ].lower()


@pytest.mark.parametrize(
    "raw_action, expected_action",
    [
        (
            '{"action":"explain","message":"This asks about your '
            'housing arrangement.","field_id":"living_arrangement"}',
            "explain",
        ),
        (
            '{"action":"clarify","message":"Do you rent, own, or stay '
            'with someone?","field_id":"living_arrangement"}',
            "clarify",
        ),
        (
            '{"action":"propose","message":"Would you like to use Rent?",'
            '"field_id":"living_arrangement","value":"Rent"}',
            "propose",
        ),
        (
            '{"action":"skip","message":"We can leave this unanswered '
            'for now.","field_id":"living_arrangement"}',
            "skip",
        ),
        (
            '{"action":"next","message":"Next, let us review your name.",'
            '"field_id":"full_name"}',
            "next",
        ),
    ],
)
def test_agent_supports_each_milestone_action(
    raw_action: str,
    expected_action: str,
) -> None:
    response = post_with_nemotron(
        StubNemotronService(raw_action),
        agent_request_payload(),
    )

    assert response.status_code == 200
    assert response.json()["action"] == expected_action


def test_next_asks_the_selected_field_instead_of_repeating_navigation() -> None:
    response = post_with_nemotron(
        StubNemotronService(
            '{"action":"next","message":"Continue to the next field.",'
            '"field_id":"full_name"}'
        ),
        agent_request_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "action": "next",
        "message": "Full name. What should be entered here?",
        "field_id": "full_name",
    }


def test_next_dropdown_question_omits_placeholder_options() -> None:
    payload = agent_request_payload()
    payload["active_field_id"] = None
    payload["message"] = "Start with the first unanswered field."
    payload["fields"][0]["status"] = "skipped"
    payload["fields"][1]["options"].insert(0, "Select one")
    nemotron = StubNemotronService(
        '{"action":"next","message":"Start with the first unanswered '
        'field.","field_id":"living_arrangement"}'
    )

    response = post_with_nemotron(nemotron, payload)

    assert response.status_code == 200
    assert response.json() == {
        "action": "next",
        "message": (
            "Which option best describes where you live? Choose one of: "
            "Rent, Own, Staying with someone."
        ),
        "field_id": "living_arrangement",
    }
    assert "Select one" not in nemotron.calls[0]["user_prompt"]


def test_dropdown_placeholder_value_becomes_unanswered() -> None:
    payload = agent_request_payload()
    payload["fields"][1].update(
        {
            "options": ["Select one", "Rent", "Own"],
            "status": "confirmed",
            "confirmed_value": "Select one",
        }
    )

    request = FormAgentRequest.model_validate(payload)
    dropdown = request.fields[1]

    assert dropdown.status == "unanswered"
    assert dropdown.confirmed_value is None
    assert dropdown.options == ["Rent", "Own"]


def test_purpose_question_uses_grounded_fallback_without_calling_model() -> None:
    payload = agent_request_payload()
    payload["message"] = "Why does the organisation need this information?"
    nemotron = StubNemotronService(
        '{"action":"explain","message":"An invented reason.",'
        '"field_id":"living_arrangement"}'
    )
    request = FormAgentRequest.model_validate(payload)

    action = asyncio.run(
        FormAgentService(nemotron).respond(request)  # type: ignore[arg-type]
    )

    assert action.action == "explain"
    assert action.field_id == "living_arrangement"
    assert "does not say why" in action.message
    assert "official instructions" in action.message
    assert nemotron.calls == []


@pytest.mark.parametrize(
    "mutate_payload",
    [
        lambda payload: payload["fields"][0].update({"type": "signature"}),
        lambda payload: payload.update({"active_field_id": "missing_field"}),
        lambda payload: payload.update(
            {
                "history": [
                    {"role": "user", "content": f"Message {index}"}
                    for index in range(9)
                ]
            }
        ),
        lambda payload: payload["fields"][2].update(
            {"confirmed_value": "false"}
        ),
    ],
)
def test_agent_rejects_invalid_client_context(mutate_payload: Any) -> None:
    payload = deepcopy(agent_request_payload())
    mutate_payload(payload)

    response = post_with_nemotron(StubNemotronService("{}"), payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "raw_action, expected_detail",
    [
        ("not JSON", "Form Agent returned an invalid action"),
        (
            '{"action":"explain","message":"Explanation",'
            '"field_id":"unknown_field"}',
            "Form Agent returned an unknown field ID",
        ),
        (
            '{"action":"propose","message":"Use this?",'
            '"field_id":"living_arrangement","value":"Lease"}',
            "Form Agent returned an invalid proposal value",
        ),
        (
            '{"action":"propose","message":"Use this?",'
            '"field_id":"living_arrangement","value":true}',
            "Form Agent returned an invalid proposal value",
        ),
    ],
)
def test_agent_rejects_invalid_model_output_with_a_controlled_error(
    raw_action: str,
    expected_detail: str,
) -> None:
    response = post_with_nemotron(
        StubNemotronService(raw_action),
        agent_request_payload(),
    )

    assert response.status_code == 502
    assert response.json() == {"detail": expected_detail}


def test_agent_returns_a_controlled_provider_error() -> None:
    response = post_with_nemotron(
        StubNemotronService(
            error=NemotronServiceError("Nebius Token Factory is unavailable")
        ),
        agent_request_payload(),
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Nebius Token Factory is unavailable"
    }


def test_next_can_finish_only_when_no_fields_are_unanswered() -> None:
    payload = agent_request_payload()
    payload["active_field_id"] = None
    for field in payload["fields"]:
        field["status"] = "skipped"
        field.pop("confirmed_value", None)

    response = post_with_nemotron(
        StubNemotronService(
            '{"action":"next","message":"All fields have been reviewed.",'
            '"field_id":null}'
        ),
        payload,
    )

    assert response.status_code == 200
    assert response.json() == {
        "action": "next",
        "message": "All supported fields have been reviewed.",
        "field_id": None,
    }


def test_next_must_select_the_first_unanswered_field() -> None:
    response = post_with_nemotron(
        StubNemotronService(
            '{"action":"next","message":"Let us review where you live.",'
            '"field_id":"living_arrangement"}'
        ),
        agent_request_payload(),
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Form Agent did not return the first unanswered field"
    }


def test_agent_cannot_skip_a_confirmed_field() -> None:
    payload = agent_request_payload()
    payload["active_field_id"] = "shares_costs"
    response = post_with_nemotron(
        StubNemotronService(
            '{"action":"skip","message":"Skipped.",'
            '"field_id":"shares_costs"}'
        ),
        payload,
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Form Agent returned a resolved field to skip"
    }


def test_form_agent_error_is_a_controlled_service_failure() -> None:
    nemotron = StubNemotronService("not JSON")
    request = FormAgentRequest.model_validate(agent_request_payload())

    with pytest.raises(FormAgentError, match="invalid action"):
        asyncio.run(
            FormAgentService(nemotron).respond(  # type: ignore[arg-type]
                request
            )
        )
