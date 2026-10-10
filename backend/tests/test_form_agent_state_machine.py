from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_form_agent_service
from app.services.form_agent import (
    FormAgentRequest,
    FormAgentService,
    FormAgentTransitionError,
)


class StubNemotronService:
    def __init__(self, response: str = "") -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.response


def request_payload(
    *,
    phase: str,
    event: dict[str, Any],
    active_field_id: str | None = None,
    pending_proposal: dict[str, Any] | None = None,
    name_status: str = "unanswered",
    include_next_field: bool = False,
) -> dict[str, Any]:
    name_field: dict[str, Any] = {
        "id": "full_name",
        "label": "Full name",
        "question": "What is your full name?",
        "type": "text",
        "status": name_status,
    }
    if name_status == "confirmed":
        name_field["confirmed_value"] = "Ada Lovelace"

    fields = [
        name_field,
        {
            "id": "shares_costs",
            "label": "Do you share household costs?",
            "type": "checkbox",
            "status": "confirmed",
            "confirmed_value": False,
        },
    ]
    if include_next_field:
        fields.append(
            {
                "id": "country",
                "label": "Country",
                "type": "dropdown",
                "options": ["United Kingdom", "United States", "Other"],
                "status": "unanswered",
            }
        )

    return {
        "fields": fields,
        "conversation_state": {
            "phase": phase,
            "active_field_id": active_field_id,
            "pending_proposal": pending_proposal,
        },
        "event": event,
    }


def respond(
    payload: dict[str, Any],
    nemotron: StubNemotronService | None = None,
):
    service = nemotron or StubNemotronService()
    response = asyncio.run(
        FormAgentService(service).respond(  # type: ignore[arg-type]
            FormAgentRequest.model_validate(payload)
        )
    )
    return response, service


def test_advance_selects_first_unanswered_field_and_declares_state() -> None:
    response, nemotron = respond(
        request_payload(phase="asking", event={"type": "advance"})
    )

    assert response.action.action == "next"
    assert response.action.field_id == "full_name"
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_answer",
        "active_field_id": "full_name",
        "pending_proposal": None,
    }
    assert nemotron.calls == []


def test_answer_proposal_enters_awaiting_confirmation_with_pending_value() -> None:
    response, nemotron = respond(
        request_payload(
            phase="awaiting_answer",
            active_field_id="full_name",
            event={"type": "message", "content": "Ada Lovelace"},
        ),
        StubNemotronService(
            '{"action":"propose","message":"Proposal",'
            '"field_id":"full_name","value":"Ada Lovelace"}'
        ),
    )

    assert response.action.action == "propose"
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_confirmation",
        "active_field_id": "full_name",
        "pending_proposal": {
            "field_id": "full_name",
            "value": "Ada Lovelace",
        },
    }
    assert len(nemotron.calls) == 0


def test_typed_reply_cannot_confirm_or_duplicate_pending_proposal() -> None:
    pending = {"field_id": "full_name", "value": "Ada Lovelace"}
    response, nemotron = respond(
        request_payload(
            phase="awaiting_confirmation",
            active_field_id="full_name",
            pending_proposal=pending,
            event={"type": "message", "content": "yes"},
        )
    )

    assert response.action.action == "clarify"
    assert "Use Confirm" in response.action.message
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_confirmation",
        "active_field_id": "full_name",
        "pending_proposal": pending,
    }
    assert nemotron.calls == []


def test_confirmation_is_a_distinct_event_and_does_not_mutate_request() -> None:
    request = FormAgentRequest.model_validate(
        request_payload(
            phase="awaiting_confirmation",
            active_field_id="full_name",
            pending_proposal={
                "field_id": "full_name",
                "value": "Ada Lovelace",
            },
            event={"type": "confirm"},
            include_next_field=True,
        )
    )

    response = asyncio.run(
        FormAgentService(StubNemotronService()).respond(  # type: ignore[arg-type]
            request
        )
    )

    assert response.action.action == "confirmed"
    assert response.action.value == "Ada Lovelace"
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_answer",
        "active_field_id": "country",
        "pending_proposal": None,
    }
    assert "Next, Country" in response.action.message
    assert request.fields[0].status == "unanswered"
    assert request.fields[1].confirmed_value is False


def test_rejection_returns_field_to_answerable_state() -> None:
    response, nemotron = respond(
        request_payload(
            phase="awaiting_confirmation",
            active_field_id="full_name",
            pending_proposal={
                "field_id": "full_name",
                "value": "Ada Lovelace",
            },
            event={"type": "reject"},
        )
    )

    assert response.action.action == "rejected"
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_answer",
        "active_field_id": "full_name",
        "pending_proposal": None,
    }
    assert "haven’t used that proposal" in response.action.message
    assert "entered instead" in response.action.message
    assert "What is your full name" in response.action.message
    assert nemotron.calls == []


def test_skip_clears_a_pending_proposal_and_asks_the_next_field() -> None:
    response, nemotron = respond(
        request_payload(
            phase="awaiting_confirmation",
            active_field_id="full_name",
            pending_proposal={
                "field_id": "full_name",
                "value": "Ada Lovelace",
            },
            event={"type": "skip", "field_id": "full_name"},
            include_next_field=True,
        )
    )

    assert response.action.action == "skip"
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_answer",
        "active_field_id": "country",
        "pending_proposal": None,
    }
    assert "Next, Country" in response.action.message
    assert nemotron.calls == []


def test_confirming_an_edited_answer_uses_the_same_progression() -> None:
    response, nemotron = respond(
        request_payload(
            phase="awaiting_confirmation",
            active_field_id="full_name",
            pending_proposal={
                "field_id": "full_name",
                "value": "Ada Example",
            },
            event={"type": "confirm_edit", "value": "Ada Lovelace"},
            include_next_field=True,
        )
    )

    assert response.action.action == "confirmed"
    assert response.action.value == "Ada Lovelace"
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_answer",
        "active_field_id": "country",
        "pending_proposal": None,
    }
    assert "Next, Country" in response.action.message
    assert nemotron.calls == []


@pytest.mark.parametrize("event_type", ["confirm", "skip"])
def test_resolving_the_final_field_completes_the_form(event_type: str) -> None:
    response, nemotron = respond(
        request_payload(
            phase="awaiting_confirmation",
            active_field_id="full_name",
            pending_proposal={
                "field_id": "full_name",
                "value": "Ada Lovelace",
            },
            event=(
                {"type": "skip", "field_id": "full_name"}
                if event_type == "skip"
                else {"type": "confirm"}
            ),
        )
    )

    assert response.action.action == (
        "confirmed" if event_type == "confirm" else "skip"
    )
    assert response.conversation_state.model_dump() == {
        "phase": "form_complete",
        "active_field_id": None,
        "pending_proposal": None,
    }
    assert "All supported fields have been reviewed" in response.action.message
    assert nemotron.calls == []


@pytest.mark.parametrize("event_type", ["confirm", "skip"])
def test_duplicate_resolution_event_is_rejected_after_progression(
    event_type: str,
) -> None:
    event = (
        {"type": "skip", "field_id": "full_name"}
        if event_type == "skip"
        else {"type": "confirm"}
    )
    first_response, _ = respond(
        request_payload(
            phase="awaiting_confirmation",
            active_field_id="full_name",
            pending_proposal={
                "field_id": "full_name",
                "value": "Ada Lovelace",
            },
            event=event,
            include_next_field=True,
        )
    )

    assert first_response.conversation_state.active_field_id == "country"
    expected_error = (
        "no longer active" if event_type == "skip" else "is not valid"
    )
    with pytest.raises(FormAgentTransitionError, match=expected_error):
        respond(
            request_payload(
                phase=first_response.conversation_state.phase,
                active_field_id=(
                    first_response.conversation_state.active_field_id
                ),
                event=event,
                name_status=(
                    "confirmed" if event_type == "confirm" else "skipped"
                ),
                include_next_field=True,
            )
        )


def test_explicit_advance_after_confirmation_can_complete_the_form() -> None:
    response, nemotron = respond(
        request_payload(
            phase="field_confirmed",
            active_field_id="full_name",
            event={"type": "advance"},
            name_status="confirmed",
        )
    )

    assert response.action.action == "next"
    assert response.action.field_id is None
    assert response.conversation_state.model_dump() == {
        "phase": "form_complete",
        "active_field_id": None,
        "pending_proposal": None,
    }
    assert nemotron.calls == []


@pytest.mark.parametrize(
    ("phase", "event", "active_field_id"),
    [
        ("asking", {"type": "confirm"}, None),
        ("awaiting_answer", {"type": "advance"}, "full_name"),
        ("field_confirmed", {"type": "message", "content": "change it"}, "full_name"),
        ("form_complete", {"type": "advance"}, None),
    ],
)
def test_invalid_phase_events_are_rejected(
    phase: str,
    event: dict[str, Any],
    active_field_id: str | None,
) -> None:
    payload = request_payload(
        phase=phase,
        active_field_id=active_field_id,
        event=event,
        name_status=("confirmed" if phase in {"field_confirmed", "form_complete"} else "unanswered"),
    )

    with pytest.raises(FormAgentTransitionError, match="is not valid"):
        respond(payload)


def test_stale_active_field_state_is_rejected_before_model_use() -> None:
    nemotron = StubNemotronService(
        '{"action":"propose","message":"Proposal",'
        '"field_id":"full_name","value":"New name"}'
    )

    with pytest.raises(FormAgentTransitionError, match="no longer answerable"):
        respond(
            request_payload(
                phase="awaiting_answer",
                active_field_id="full_name",
                event={"type": "message", "content": "New name"},
                name_status="confirmed",
            ),
            nemotron,
        )

    assert nemotron.calls == []


def test_invalid_transition_returns_controlled_conflict_response() -> None:
    service = FormAgentService(StubNemotronService())  # type: ignore[arg-type]
    app.dependency_overrides[get_form_agent_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/agent/respond",
            json=request_payload(
                phase="awaiting_answer",
                active_field_id="full_name",
                event={"type": "advance"},
            ),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            'Event "advance" is not valid while the conversation is in '
            'phase "awaiting_answer"'
        )
    }
