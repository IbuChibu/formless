from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services.form_agent import (
    FormAgentRequest,
    FormAgentService,
    FormAgentTransitionError,
)


class StubNemotronService:
    def __init__(self, response: str = "not valid json") -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.response


def field(
    field_id: str,
    label: str,
    *,
    status: str = "unanswered",
    value: str | bool | None = None,
    section: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": field_id,
        "label": label,
        "question": question or f"What is your {label.lower()}?",
        "type": "text",
        "status": status,
    }
    if value is not None:
        result["confirmed_value"] = value
    if section is not None:
        result["section"] = section
    return result


def request(
    *,
    fields: list[dict[str, Any]],
    phase: str,
    event: dict[str, Any],
    active_field_id: str | None = None,
    pending_proposal: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> FormAgentRequest:
    return FormAgentRequest.model_validate(
        {
            "fields": fields,
            "conversation_state": {
                "phase": phase,
                "active_field_id": active_field_id,
                "pending_proposal": pending_proposal,
            },
            "event": event,
            "history": history or [],
        }
    )


def respond(
    agent_request: FormAgentRequest,
    nemotron: StubNemotronService | None = None,
):
    provider = nemotron or StubNemotronService()
    response = asyncio.run(
        FormAgentService(  # type: ignore[arg-type]
            provider,
            turn_interpretation_enabled=False,
        ).respond(agent_request)
    )
    return response, provider


def test_conversation_selects_a_later_unanswered_field_without_mutation() -> None:
    fields = [
        field("work_address", "Work address"),
        field("date_of_birth", "Date of birth"),
    ]
    agent_request = request(
        fields=fields,
        phase="awaiting_answer",
        active_field_id="work_address",
        event={"type": "message", "content": "Go to date of birth."},
    )

    response, nemotron = respond(agent_request)

    assert response.effect.model_dump() == {
        "effect": "field_selected",
        "field_id": "date_of_birth",
    }
    assert response.conversation_state.model_dump() == {
        "phase": "awaiting_answer",
        "active_field_id": "date_of_birth",
        "pending_proposal": None,
    }
    assert "What is your date of birth?" in response.assistant_message
    assert all(item.status == "unanswered" for item in agent_request.fields)
    assert nemotron.calls == []


def test_ambiguous_field_reference_lists_matches_without_selecting() -> None:
    agent_request = request(
        fields=[
            field("work_address", "Work address"),
            field("mailing_address", "Mailing address"),
        ],
        phase="awaiting_answer",
        active_field_id="work_address",
        event={"type": "message", "content": "Go to the address field."},
    )

    response, nemotron = respond(agent_request)

    assert response.effect.effect == "none"
    assert response.conversation_state == agent_request.conversation_state
    assert "more than one" in response.assistant_message
    assert "work address" in response.assistant_message
    assert "mailing address" in response.assistant_message
    assert nemotron.calls == []


def test_skipped_field_reopens_and_uses_the_normal_proposal_flow() -> None:
    completed_fields = [
        field("full_name", "Full name", status="confirmed", value="Ada Lovelace"),
        field("home_address", "Home address", status="skipped"),
    ]
    reopen_request = request(
        fields=completed_fields,
        phase="form_complete",
        event={"type": "message", "content": "Reopen my home address."},
    )

    reopened, nemotron = respond(reopen_request)

    assert reopened.effect.model_dump() == {
        "effect": "field_reopened",
        "field_id": "home_address",
    }
    assert reopened.conversation_state.phase == "awaiting_answer"
    assert reopen_request.fields[1].status == "skipped"
    assert nemotron.calls == []

    reopened_fields = [completed_fields[0], field("home_address", "Home address")]
    proposal, nemotron = respond(
        request(
            fields=reopened_fields,
            phase="awaiting_answer",
            active_field_id="home_address",
            event={
                "type": "message",
                "content": "10 Downing Street, London",
            },
        )
    )

    assert proposal.effect.effect == "proposal"
    assert proposal.effect.field_id == "home_address"
    assert proposal.conversation_state.phase == "awaiting_confirmation"
    assert nemotron.calls == []


def test_replacement_rejection_and_cancellation_preserve_confirmed_value() -> None:
    canonical_fields = [
        field("full_name", "Full name", status="confirmed", value="Ada Lovelace")
    ]
    correction, _ = respond(
        request(
            fields=canonical_fields,
            phase="form_complete",
            event={"type": "message", "content": "Change my full name."},
        )
    )

    assert correction.effect.effect == "correction_started"
    assert correction.conversation_state.phase == "awaiting_replacement"
    assert correction.assistant_message.count("Ada Lovelace") == 1
    assert canonical_fields[0]["confirmed_value"] == "Ada Lovelace"

    proposal_request = request(
        fields=canonical_fields,
        phase="awaiting_replacement",
        active_field_id="full_name",
        event={"type": "message", "content": "grace hopper"},
    )
    proposal, _ = respond(proposal_request)

    assert proposal.effect.model_dump() == {
        "effect": "replacement_proposal",
        "field_id": "full_name",
        "previous_confirmed_value": "Ada Lovelace",
        "original_value": "grace hopper",
        "prepared_value": "Grace Hopper",
        "transformation": (
            "Capitalization suggested; spelling and letter order preserved."
        ),
    }
    assert proposal.conversation_state.model_dump() == {
        "phase": "awaiting_replacement_confirmation",
        "active_field_id": "full_name",
        "pending_proposal": {
            "operation": "replacement",
            "field_id": "full_name",
            "previous_confirmed_value": "Ada Lovelace",
            "value": "Grace Hopper",
        },
    }
    assert proposal_request.fields[0].confirmed_value == "Ada Lovelace"

    typed_acknowledgement, _ = respond(
        request(
            fields=canonical_fields,
            phase="awaiting_replacement_confirmation",
            active_field_id="full_name",
            pending_proposal=proposal.conversation_state.pending_proposal.model_dump(),
            event={"type": "message", "content": "yes"},
        )
    )
    assert typed_acknowledgement.effect.effect == "none"
    assert (
        typed_acknowledgement.conversation_state
        == proposal.conversation_state
    )
    assert canonical_fields[0]["confirmed_value"] == "Ada Lovelace"

    rejected, _ = respond(
        request(
            fields=canonical_fields,
            phase="awaiting_replacement_confirmation",
            active_field_id="full_name",
            pending_proposal=proposal.conversation_state.pending_proposal.model_dump(),
            event={"type": "reject"},
        )
    )
    assert rejected.effect.effect == "rejected"
    assert rejected.conversation_state.phase == "form_complete"
    assert canonical_fields[0]["confirmed_value"] == "Ada Lovelace"

    cancelled, _ = respond(
        request(
            fields=canonical_fields,
            phase="awaiting_replacement",
            active_field_id="full_name",
            event={"type": "message", "content": "Cancel this correction."},
        )
    )
    assert cancelled.effect.effect == "correction_cancelled"
    assert cancelled.conversation_state.phase == "form_complete"
    assert "remains \"Ada Lovelace\"" in cancelled.assistant_message


def test_natural_return_and_cancellation_use_closed_correction_flow() -> None:
    fields = [
        field("full_name", "Full name", status="confirmed", value="Taylor Reed"),
        field("country", "Country"),
    ]
    correction, provider = respond(
        request(
            fields=fields,
            phase="awaiting_answer",
            active_field_id="country",
            event={
                "type": "message",
                "content": "Can we go back to the full name question?",
            },
        )
    )

    assert correction.effect.effect == "correction_started"
    assert correction.conversation_state.phase == "awaiting_replacement"
    assert correction.conversation_state.active_field_id == "full_name"
    assert "Taylor Reed" in correction.assistant_message
    assert fields[0]["confirmed_value"] == "Taylor Reed"
    assert provider.calls == []

    cancelled, provider = respond(
        request(
            fields=fields,
            phase="awaiting_replacement",
            active_field_id="full_name",
            event={
                "type": "message",
                "content": "Actually it was right, cancel that correction.",
            },
        )
    )

    assert cancelled.effect.effect == "correction_cancelled"
    assert cancelled.conversation_state.phase == "awaiting_answer"
    assert cancelled.conversation_state.active_field_id == "country"
    assert "country" in cancelled.assistant_message.casefold()
    assert fields[0]["confirmed_value"] == "Taylor Reed"
    assert provider.calls == []


def test_explicit_reference_recovers_one_prior_volunteered_date() -> None:
    date_field = field(
        "date_of_birth",
        "Date of birth",
        question="Date of birth (DD/MM/YYYY)",
    )
    proposal, provider = respond(
        request(
            fields=[date_field],
            phase="awaiting_answer",
            active_field_id="date_of_birth",
            event={
                "type": "message",
                "content": "I already gave you my date of birth with my name.",
            },
            history=[
                {
                    "role": "user",
                    "content": (
                        "My full legal name is Mina Okafor, and I was born "
                        "on 6 March 1992."
                    ),
                },
                {
                    "role": "assistant",
                    "content": "Thanks. Your name is awaiting confirmation.",
                },
            ],
        )
    )

    assert proposal.effect.model_dump() == {
        "effect": "proposal",
        "field_id": "date_of_birth",
        "original_value": "6 March 1992",
        "prepared_value": "06/03/1992",
        "transformation": "Formatted to match the date format requested.",
    }
    assert proposal.conversation_state.phase == "awaiting_confirmation"
    assert provider.calls == []


def test_prior_answer_recovery_clarifies_when_dates_conflict() -> None:
    date_field = field(
        "date_of_birth",
        "Date of birth",
        question="Date of birth (DD/MM/YYYY)",
    )
    response, provider = respond(
        request(
            fields=[date_field],
            phase="awaiting_answer",
            active_field_id="date_of_birth",
            event={
                "type": "message",
                "content": "I already gave you my date of birth.",
            },
            history=[
                {
                    "role": "user",
                    "content": "I was born on 6 March 1992.",
                },
                {
                    "role": "user",
                    "content": "My date of birth is 7 March 1992.",
                },
            ],
        )
    )

    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "awaiting_clarification"
    assert "more than one earlier date" in response.assistant_message
    assert provider.calls == []


def test_edit_confirmation_replaces_once_and_duplicate_event_is_stale() -> None:
    canonical_fields = [
        field("full_name", "Full name", status="confirmed", value="Ada Lovelace"),
        field("date_of_birth", "Date of birth"),
    ]
    pending = {
        "operation": "replacement",
        "field_id": "full_name",
        "previous_confirmed_value": "Ada Lovelace",
        "value": "Grace Hopper",
    }
    confirmation_request = request(
        fields=canonical_fields,
        phase="awaiting_replacement_confirmation",
        active_field_id="full_name",
        pending_proposal=pending,
        event={"type": "confirm_edit", "value": "Katherine Johnson"},
    )

    confirmed, nemotron = respond(confirmation_request)

    assert confirmed.effect.model_dump() == {
        "effect": "confirmed",
        "field_id": "full_name",
        "value": "Katherine Johnson",
    }
    assert confirmed.conversation_state.phase == "awaiting_answer"
    assert confirmed.conversation_state.active_field_id == "date_of_birth"
    assert "your edited value" in confirmed.assistant_message
    assert "Katherine Johnson" in confirmed.assistant_message
    assert confirmation_request.fields[0].confirmed_value == "Ada Lovelace"
    assert nemotron.calls == []

    with pytest.raises(FormAgentTransitionError, match="is not valid"):
        respond(
            request(
                fields=[
                    field(
                        "full_name",
                        "Full name",
                        status="confirmed",
                        value="Katherine Johnson",
                    ),
                    field("date_of_birth", "Date of birth"),
                ],
                phase="awaiting_answer",
                active_field_id="date_of_birth",
                event={"type": "confirm"},
            )
        )


def test_stale_replacement_confirmation_is_rejected_before_any_model_call() -> None:
    nemotron = StubNemotronService()
    with pytest.raises(FormAgentTransitionError, match="stale"):
        respond(
            request(
                fields=[
                    field(
                        "full_name",
                        "Full name",
                        status="confirmed",
                        value="A newer value",
                    )
                ],
                phase="awaiting_replacement_confirmation",
                active_field_id="full_name",
                pending_proposal={
                    "operation": "replacement",
                    "field_id": "full_name",
                    "previous_confirmed_value": "Ada Lovelace",
                    "value": "Grace Hopper",
                },
                event={"type": "confirm"},
            ),
            nemotron,
        )
    assert nemotron.calls == []


def test_specific_value_review_is_grounded_in_canonical_state() -> None:
    canonical_fields = [
        field("full_name", "Full name", status="confirmed", value="Ada Lovelace"),
        field("home_address", "Home address", status="skipped"),
    ]
    agent_request = request(
        fields=canonical_fields,
        phase="form_complete",
        event={"type": "message", "content": "What did I put for full name?"},
    )

    response, nemotron = respond(agent_request)

    assert response.effect.effect == "none"
    assert response.conversation_state == agent_request.conversation_state
    assert 'is "Ada Lovelace"' in response.assistant_message
    assert nemotron.calls == []


@pytest.mark.parametrize("phase", ["awaiting_answer", "form_complete"])
def test_status_review_lists_canonical_fields_without_mutation(phase: str) -> None:
    fields = [
        field("full_name", "Full name", status="confirmed", value="Ada Lovelace"),
        field("home_address", "Home address", status="skipped"),
    ]
    active_field_id = None
    if phase == "awaiting_answer":
        fields.append(field("date_of_birth", "Date of birth"))
        active_field_id = "date_of_birth"
    agent_request = request(
        fields=fields,
        phase=phase,
        active_field_id=active_field_id,
        event={
            "type": "message",
            "content": "Show confirmed, skipped, and unanswered fields.",
        },
    )

    response, nemotron = respond(agent_request)

    assert response.effect.effect == "none"
    assert response.conversation_state == agent_request.conversation_state
    assert "Confirmed (1): What is your full name" in response.assistant_message
    assert "Skipped (1): What is your home address" in response.assistant_message
    expected_unanswered = 1 if phase == "awaiting_answer" else 0
    assert f"Unanswered ({expected_unanswered})" in response.assistant_message
    assert nemotron.calls == []


def test_invalid_model_output_during_correction_preserves_previous_value() -> None:
    canonical_fields = [
        field("full_name", "Full name", status="confirmed", value="Ada Lovelace"),
        field("date_of_birth", "Date of birth"),
    ]
    agent_request = request(
        fields=canonical_fields,
        phase="awaiting_replacement",
        active_field_id="full_name",
        event={"type": "message", "content": "Can we pause?"},
    )

    response, nemotron = respond(agent_request, StubNemotronService())

    assert response.effect.effect == "none"
    assert response.conversation_state == agent_request.conversation_state
    assert agent_request.fields[0].confirmed_value == "Ada Lovelace"
    assert len(nemotron.calls) == 2
