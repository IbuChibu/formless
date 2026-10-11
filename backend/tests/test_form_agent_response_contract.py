from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services.form_agent import (
    ConversationState,
    FormAgentField,
    FormAgentRequest,
    FormAgentService,
)
from app.services.form_agent.answer_preparation import prepare_answer
from app.services.form_agent.prompt_builder import build_agent_context


class StubNemotronService:
    def __init__(self, response: str = "not used") -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.response


def _field(
    *,
    field_id: str = "full_name",
    label: str = "Full name",
    question: str | None = None,
    field_type: str = "text",
    status: str = "unanswered",
    confirmed_value: str | bool | None = None,
    options: list[str] | None = None,
) -> FormAgentField:
    return FormAgentField.model_validate(
        {
            "id": field_id,
            "label": label,
            "question": question or label,
            "type": field_type,
            "status": status,
            "confirmed_value": confirmed_value,
            "options": options,
        }
    )


def _request(
    field: FormAgentField,
    message: str,
    *,
    state: ConversationState | None = None,
) -> FormAgentRequest:
    return FormAgentRequest.model_validate(
        {
            "form_context": {
                "title": "Test form",
                "instructions": [],
            },
            "fields": [field.model_dump()],
            "conversation_state": (
                state.model_dump()
                if state is not None
                else {
                    "phase": "awaiting_answer",
                    "active_field_id": field.id,
                    "pending_proposal": None,
                }
            ),
            "event": {"type": "message", "content": message},
            "history": [],
        }
    )


def test_conversation_response_separates_message_from_non_mutating_effect() -> None:
    request = _request(_field(), "What does this mean?")
    service = FormAgentService(  # type: ignore[arg-type]
        StubNemotronService(
            '{"action":"explain","message":"It asks for your full name.",'
            '"field_id":"full_name"}'
        )
    )

    response = asyncio.run(service.respond(request))
    payload = response.model_dump()

    assert payload["assistant_message"] == "It asks for your full name."
    assert payload["effect"] == {
        "effect": "none",
        "field_id": "full_name",
    }
    assert "action" not in payload
    assert response.conversation_state == request.conversation_state


def test_lowercase_name_returns_original_and_reviewable_capitalization() -> None:
    request = _request(_field(), "my name is john smith")
    nemotron = StubNemotronService()

    response = asyncio.run(
        FormAgentService(nemotron).respond(request)  # type: ignore[arg-type]
    )
    effect = response.effect

    assert effect.effect == "proposal"
    assert effect.original_value == "john smith"  # type: ignore[union-attr]
    assert effect.prepared_value == "John Smith"  # type: ignore[union-attr]
    assert "Capitalization suggested" in (  # type: ignore[union-attr]
        effect.transformation or ""
    )
    assert response.conversation_state.pending_proposal is not None
    assert response.conversation_state.pending_proposal.value == "John Smith"
    assert nemotron.calls == []


@pytest.mark.parametrize(
    "name",
    ["McDonald", "O'Neill", "Smith-Jones", "de la Cruz", "MARIA SILVA"],
)
def test_existing_name_spelling_and_meaningful_casing_are_preserved(
    name: str,
) -> None:
    prepared = prepare_answer(_field(), name, name)

    assert prepared.prepared_value == name
    assert prepared.transformation is None


def test_non_english_lowercase_name_only_changes_capitalization() -> None:
    prepared = prepare_answer(_field(), "josé álvarez", "josé álvarez")

    assert prepared.prepared_value == "José Álvarez"
    assert prepared.original_value == "josé álvarez"


def test_date_preparation_exposes_requested_format_without_losing_original() -> None:
    field = _field(
        field_id="dob",
        label="Date of birth (DD/MM/YYYY)",
    )
    request = _request(field, "I was born on 17 October 1986")

    response = asyncio.run(
        FormAgentService(StubNemotronService()).respond(  # type: ignore[arg-type]
            request
        )
    )
    effect = response.effect

    assert effect.effect == "proposal"
    assert effect.original_value == "17 October 1986"  # type: ignore[union-attr]
    assert effect.prepared_value == "17/10/1986"  # type: ignore[union-attr]
    assert "date format" in effect.transformation  # type: ignore[union-attr]


def test_identity_spelling_is_not_guessed() -> None:
    prepared = prepare_answer(_field(), "jon smth", "jon smth")

    assert prepared.original_value == "jon smth"
    assert prepared.prepared_value == "Jon Smth"
    assert "spelling" in (prepared.transformation or "")
    assert "John Smith" not in str(prepared.prepared_value)


@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("Home address", "10 Main Street, London"),
        ("Postcode", "SW1A 1AA"),
        ("Phone number", "+44 20 7946 0018"),
        ("Email address", "Name.Example+tag@example.com"),
        ("Passport number", "AB1234567"),
        ("Account reference", "REF-00A91"),
    ],
)
def test_address_and_identifier_characters_are_preserved(
    label: str,
    value: str,
) -> None:
    prepared = prepare_answer(
        _field(field_id="value", label=label),
        value,
        value,
    )

    assert prepared.prepared_value == value
    assert prepared.transformation is None


def test_prose_polish_preserves_words_negation_dates_and_quantities() -> None:
    field = _field(
        field_id="reason",
        label="Reason for leaving",
        field_type="textarea",
    )
    original = "i did not work 3 nights after 12 June 2019"

    prepared = prepare_answer(field, original, original)

    assert prepared.prepared_value == (
        "I did not work 3 nights after 12 June 2019."
    )
    assert "did not" in str(prepared.prepared_value)
    assert "3" in str(prepared.prepared_value)
    assert "12 June 2019" in str(prepared.prepared_value)


def test_prose_polish_preserves_uncertainty_and_stated_reason() -> None:
    field = _field(
        field_id="reason",
        label="Additional explanation",
        field_type="textarea",
    )
    original = "i may need to leave because the hours might change"

    prepared = prepare_answer(field, original, original)

    assert prepared.prepared_value == (
        "I may need to leave because the hours might change."
    )
    assert "may" in str(prepared.prepared_value)
    assert "might" in str(prepared.prepared_value)


def test_explicit_prose_tidy_returns_a_reviewable_model_suggestion() -> None:
    field = _field(
        field_id="reason",
        label="Reason for leaving",
        field_type="textarea",
    )
    request = _request(
        field,
        "Please tidy this: i left because the hours was changed and i could not do nights",
    )
    nemotron = StubNemotronService(
        '{"action":"propose","message":"Here is a clearer version for '
        'review.","field_id":"reason","value":"I left because the hours '
        'were changed and I could not do nights."}'
    )

    response = asyncio.run(
        FormAgentService(nemotron).respond(request)  # type: ignore[arg-type]
    )

    assert response.effect.effect == "proposal"
    assert response.effect.original_value == (  # type: ignore[union-attr]
        "i left because the hours was changed and i could not do nights"
    )
    assert response.effect.prepared_value == (  # type: ignore[union-attr]
        "I left because the hours were changed and I could not do nights."
    )
    assert "Grammar and presentation suggested" in (  # type: ignore[union-attr]
        response.effect.transformation or ""
    )
    assert response.conversation_state.phase == "awaiting_confirmation"
    assert len(nemotron.calls) == 1


def test_unsafe_prose_tidy_falls_back_to_the_original_wording() -> None:
    field = _field(
        field_id="reason",
        label="Reason for leaving",
        field_type="textarea",
    )
    original = "i did not work 3 nights because the hours changed"
    request = _request(field, f"Polish this: {original}")
    unsafe = (
        '{"action":"propose","message":"Suggestion",'
        '"field_id":"reason","value":"I worked 3 days because the hours changed."}'
    )
    nemotron = StubNemotronService(unsafe)

    response = asyncio.run(
        FormAgentService(nemotron).respond(request)  # type: ignore[arg-type]
    )

    assert response.effect.effect == "proposal"
    assert response.effect.original_value == original  # type: ignore[union-attr]
    assert response.effect.prepared_value == original  # type: ignore[union-attr]
    assert response.effect.transformation is None  # type: ignore[union-attr]
    assert "kept your original text" in response.assistant_message
    assert len(nemotron.calls) == 2


def test_use_original_can_be_confirmed_through_explicit_edit_event() -> None:
    request = _request(_field(), "my name is john smith")
    proposal_response = asyncio.run(
        FormAgentService(StubNemotronService()).respond(  # type: ignore[arg-type]
            request
        )
    )
    confirm_request = FormAgentRequest.model_validate(
        {
            **request.model_dump(),
            "conversation_state": (
                proposal_response.conversation_state.model_dump()
            ),
            "event": {"type": "confirm_edit", "value": "john smith"},
        }
    )

    confirmed = asyncio.run(
        FormAgentService(StubNemotronService()).respond(  # type: ignore[arg-type]
            confirm_request
        )
    )

    assert confirmed.effect.effect == "confirmed"
    assert confirmed.effect.value == "john smith"  # type: ignore[union-attr]


def test_working_memory_includes_only_explicitly_referenced_confirmed_value() -> None:
    fields = [
        _field(
            field_id="home_address",
            label="Home address",
            status="confirmed",
            confirmed_value="10 Main Street",
        ),
        _field(
            field_id="date_of_birth",
            label="Date of birth",
            status="confirmed",
            confirmed_value="17/10/1986",
        ),
        _field(field_id="mailing_address", label="Mailing address"),
    ]
    request = FormAgentRequest.model_validate(
        {
            "form_context": {"title": "Test form", "instructions": []},
            "fields": [field.model_dump() for field in fields],
            "conversation_state": {
                "phase": "awaiting_answer",
                "active_field_id": "mailing_address",
                "pending_proposal": None,
            },
            "event": {
                "type": "message",
                "content": "Can I use my home address here?",
            },
            "history": [],
        }
    )

    context = build_agent_context(request)
    working_memory = context["working_memory"]

    assert isinstance(working_memory, dict)
    assert working_memory["relevant_confirmed_answers"] == [
        {
            "field_id": "home_address",
            "label": "Home address",
            "value": "10 Main Street",
        }
    ]
    assert "17/10/1986" not in str(working_memory)
