from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.form_agent import FormAgentRequest, FormAgentService
from app.services.form_agent.answer_adapters import (
    MatchedAnswer,
    interpret_answer,
    merge_volunteered_candidates,
)


class StubNemotronService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "not valid json"


def _field(
    field_id: str,
    label: str,
    *,
    field_type: str = "text",
    question: str | None = None,
    help_text: str | None = None,
    options: list[str] | None = None,
    status: str = "unanswered",
    value: str | bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": field_id,
        "label": label,
        "question": question or label,
        "type": field_type,
        "status": status,
    }
    if help_text is not None:
        result["help_text"] = help_text
    if options is not None:
        result["options"] = options
    if value is not None:
        result["confirmed_value"] = value
    return result


def _request(
    fields: list[dict[str, Any]],
    *,
    phase: str,
    event: dict[str, Any],
    active_field_id: str | None = None,
    pending_proposal: dict[str, Any] | None = None,
    remembered_candidates: list[dict[str, Any]] | None = None,
) -> FormAgentRequest:
    return FormAgentRequest.model_validate(
        {
            "fields": fields,
            "conversation_state": {
                "phase": phase,
                "active_field_id": active_field_id,
                "pending_proposal": pending_proposal,
                "remembered_candidates": remembered_candidates or [],
            },
            "event": event,
            "history": [],
        }
    )


def _respond(request: FormAgentRequest):
    nemotron = StubNemotronService()
    response = asyncio.run(
        FormAgentService(  # type: ignore[arg-type]
            nemotron,
            turn_interpretation_enabled=False,
        ).respond(request)
    )
    return response, nemotron


def _bundled_fields(*, name_confirmed: bool = False) -> list[dict[str, Any]]:
    return [
        _field(
            "applicant_full_legal_name",
            "Full legal name",
            question="Your full legal name as it appears on official records",
            status="confirmed" if name_confirmed else "unanswered",
            value="Maya Patel" if name_confirmed else None,
        ),
        _field(
            "applicant_date_of_birth",
            "Date of birth",
            question="Date of birth (DD/MM/YYYY)",
        ),
        _field(
            "residency_arrangement",
            "Housing arrangement",
            field_type="dropdown",
            options=["Sole tenant", "Joint tenant", "Owner-occupier"],
        ),
    ]


def test_bundled_message_proposes_active_answer_and_remembers_later_values() -> None:
    response, nemotron = _respond(
        _request(
            _bundled_fields(),
            phase="awaiting_answer",
            active_field_id="applicant_full_legal_name",
            event={
                "type": "message",
                "content": (
                    "My legal name is Maya Patel, I was born on 9 April "
                    "1990, and I am a sole tenant."
                ),
            },
        )
    )

    assert response.effect.effect == "proposal"
    assert response.effect.prepared_value == "Maya Patel"
    assert [
        candidate.model_dump()
        for candidate in response.conversation_state.remembered_candidates
    ] == [
        {
            "field_id": "applicant_date_of_birth",
            "original_value": "9 April 1990",
            "value": "09/04/1990",
        },
        {
            "field_id": "residency_arrangement",
            "original_value": "Sole tenant",
            "value": "Sole tenant",
        },
    ]
    assert nemotron.calls == []


def test_explicit_reference_offers_remembered_value_without_reasking() -> None:
    remembered = [
        {
            "field_id": "applicant_date_of_birth",
            "original_value": "9 April 1990",
            "value": "09/04/1990",
        },
        {
            "field_id": "residency_arrangement",
            "original_value": "Sole tenant",
            "value": "Sole tenant",
        },
    ]
    response, nemotron = _respond(
        _request(
            _bundled_fields(name_confirmed=True),
            phase="awaiting_answer",
            active_field_id="applicant_date_of_birth",
            remembered_candidates=remembered,
            event={
                "type": "message",
                "content": "I already gave you my date of birth with my name.",
            },
        )
    )

    assert response.effect.effect == "proposal"
    assert response.effect.prepared_value == "09/04/1990"
    assert response.conversation_state.remembered_candidates[0].field_id == (
        "applicant_date_of_birth"
    )
    assert nemotron.calls == []


def test_conflicting_volunteered_values_are_not_remembered() -> None:
    fields = [
        FormAgentRequest.model_validate(
            {
                "fields": _bundled_fields(),
                "conversation_state": {
                    "phase": "asking",
                    "active_field_id": None,
                    "pending_proposal": None,
                },
                "event": {"type": "advance"},
            }
        ).fields[1]
    ]
    candidates = merge_volunteered_candidates(
        [],
        fields,
        None,
        (
            "My date of birth is 9 April 1990, and my date of birth is "
            "10 April 1990."
        ),
        interpret_answer,
        max_candidates=5,
    )

    assert candidates == []


@pytest.mark.parametrize(
    ("label", "message", "expected"),
    [
        ("Last Name (Family Name)", "Okafor.", "Okafor"),
        ("Employee Middle Initial (if any)", "I am back. It is J.", "J"),
        ("City or Town", "The city is Bath.", "Bath"),
        ("Apt Number (if any)", "Apartment 4B", "4B"),
    ],
)
def test_conversational_wrappers_are_removed_conservatively(
    label: str,
    message: str,
    expected: str,
) -> None:
    result = interpret_answer(
        FormAgentRequest.model_validate(
            {
                "fields": [_field("value", label)],
                "conversation_state": {
                    "phase": "asking",
                    "active_field_id": None,
                    "pending_proposal": None,
                },
                "event": {"type": "advance"},
            }
        ).fields[0],
        message,
    )

    assert isinstance(result, MatchedAnswer)
    assert result.value == expected
    assert result.original_value


def test_name_cleanup_preserves_meaningful_internal_punctuation() -> None:
    name_field = FormAgentRequest.model_validate(
        {
            "fields": [_field("name", "Full legal name")],
            "conversation_state": {
                "phase": "asking",
                "active_field_id": None,
                "pending_proposal": None,
            },
            "event": {"type": "advance"},
        }
    ).fields[0]

    result = interpret_answer(name_field, "O'Neill-Smith.")

    assert isinstance(result, MatchedAnswer)
    assert result.value == "O'Neill-Smith"


def test_count_yourself_question_is_answered_without_navigation_or_mutation() -> None:
    response, nemotron = _respond(
        _request(
            [
                _field(
                    "household_member_count",
                    "Household member count",
                    field_type="number",
                    question="How many people ordinarily live at this address?",
                    help_text="Count yourself and everyone who normally lives here.",
                )
            ],
            phase="awaiting_answer",
            active_field_id="household_member_count",
            event={
                "type": "message",
                "content": "Do I count myself even though I live alone?",
            },
        )
    )

    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "awaiting_answer"
    assert response.conversation_state.active_field_id == "household_member_count"
    assert "count yourself" in response.assistant_message
    assert "1" in response.assistant_message
    assert nemotron.calls == []


def test_post_completion_specific_review_uses_canonical_state() -> None:
    fields = [
        _field(
            "last_name",
            "Last Name (Family Name)",
            status="confirmed",
            value="Okafor",
        ),
        _field("middle", "Middle initial", status="skipped"),
    ]
    value_response, _ = _respond(
        _request(
            fields,
            phase="form_complete",
            event={"type": "message", "content": "What surname did we put down?"},
        )
    )
    skipped_response, _ = _respond(
        _request(
            fields,
            phase="form_complete",
            event={"type": "message", "content": "Did I skip anything?"},
        )
    )

    assert value_response.effect.effect == "none"
    assert value_response.conversation_state.phase == "form_complete"
    assert "Okafor" in value_response.assistant_message
    assert skipped_response.effect.effect == "none"
    assert "Middle initial" in skipped_response.assistant_message


def test_post_completion_readback_lists_confirmed_values_before_completion_summary() -> None:
    response, _ = _respond(
        _request(
            [
                _field(
                    "applicant_full_legal_name",
                    "Full legal name",
                    status="confirmed",
                    value="Maya Patel",
                ),
                _field(
                    "applicant_preferred_name",
                    "Name you want us to use",
                    status="confirmed",
                    value="Maya",
                ),
                _field(
                    "applicant_date_of_birth",
                    "Date of birth (DD/MM/YYYY)",
                    status="confirmed",
                    value="09/04/1990",
                ),
            ],
            phase="form_complete",
            event={"type": "message", "content": "Read all three back once."},
        )
    )

    assert response.effect.effect == "none"
    assert response.conversation_state.phase == "form_complete"
    assert "Maya Patel" in response.assistant_message
    assert '"Maya"' in response.assistant_message
    assert '"09/04/1990"' in response.assistant_message


def test_post_completion_correction_keeps_existing_value_until_confirmation() -> None:
    response, nemotron = _respond(
        _request(
            [
                _field(
                    "country",
                    "Country",
                    status="confirmed",
                    value="United Kingdom",
                )
            ],
            phase="form_complete",
            event={"type": "message", "content": "I might change my country."},
        )
    )

    assert response.effect.effect == "correction_started"
    assert response.conversation_state.phase == "awaiting_replacement"
    assert "United Kingdom" in response.assistant_message
    assert nemotron.calls == []


@pytest.mark.parametrize(
    ("message", "expected_field_id"),
    [
        ("Change the rent budget amount.", "budget"),
        ("I found the payslip. Change employment income.", "employment"),
    ],
)
def test_correction_reference_prefers_the_specific_confirmed_field(
    message: str,
    expected_field_id: str,
) -> None:
    fields = [
        _field(
            "rent_item",
            "Monthly rent expense 1",
            question="Rent Budget item 1, edit to change item",
            status="confirmed",
            value="Studio rent",
        ),
        _field(
            "budget",
            "Monthly budget cost 1",
            field_type="number",
            question="Rent Monthly budget amount 1, edit to change amount",
            status="confirmed",
            value="1500",
        ),
        _field(
            "actual",
            "Monthly actual cost 1",
            field_type="number",
            question="Rent Monthly actual amount 1, edit to change amount",
            status="confirmed",
            value="1400",
        ),
        _field(
            "employment",
            "Gross employment resources",
            field_type="number",
            question="Aggregate gross employment receipts",
            status="confirmed",
            value="2000",
        ),
        _field(
            "nonemployment",
            "Gross non-employment resources",
            field_type="number",
            question="Aggregate non-employment resources",
            status="confirmed",
            value="0",
        ),
    ]
    response, nemotron = _respond(
        _request(
            fields,
            phase="form_complete",
            event={"type": "message", "content": message},
        )
    )

    assert response.effect.effect == "correction_started"
    assert response.effect.field_id == expected_field_id
    assert nemotron.calls == []


def test_conversational_reopen_and_cancel_use_closed_transitions() -> None:
    reopened, _ = _respond(
        _request(
            [
                _field(
                    "preferred_name",
                    "Preferred name",
                    status="skipped",
                ),
                _field(
                    "legal_name",
                    "Legal name",
                    status="confirmed",
                    value="Eli Morgan",
                ),
            ],
            phase="form_complete",
            event={
                "type": "message",
                "content": "Let's go back to the preferred name.",
            },
        )
    )
    assert reopened.effect.effect == "field_reopened"
    assert reopened.conversation_state.phase == "awaiting_answer"

    cancelled, _ = _respond(
        _request(
            [
                _field(
                    "accept_terms",
                    "Accept terms",
                    field_type="checkbox",
                    status="confirmed",
                    value=False,
                )
            ],
            phase="awaiting_replacement",
            active_field_id="accept_terms",
            event={
                "type": "message",
                "content": "Actually leave it unchanged and cancel.",
            },
        )
    )
    assert cancelled.effect.effect == "correction_cancelled"
    assert cancelled.conversation_state.phase == "form_complete"


def test_free_text_answer_containing_help_is_still_a_candidate() -> None:
    response, nemotron = _respond(
        _request(
            [
                _field(
                    "explanation",
                    "Support request explanation",
                    field_type="textarea",
                    question=(
                        "Explain what happened, what help you need, what you "
                        "have already tried, and what happened next"
                    ),
                )
            ],
            phase="awaiting_answer",
            active_field_id="explanation",
            event={
                "type": "message",
                "content": (
                    "My work hours were reduced, I need help buying food, "
                    "and my family cannot help."
                ),
            },
        )
    )

    assert response.effect.effect == "proposal"
    assert "work hours" in str(response.effect.prepared_value)
    assert nemotron.calls == []


def test_simple_rephrase_acknowledges_frustration_and_preserves_state() -> None:
    fields = [
        _field(
            "occupancy_start_date",
            "Date occupancy commenced",
            question="Date occupancy commenced",
        )
    ]
    frustrated, nemotron = _respond(
        _request(
            fields,
            phase="awaiting_answer",
            active_field_id="occupancy_start_date",
            event={
                "type": "message",
                "content": "This wording is exhausting. I do not understand it.",
            },
        )
    )
    simpler, _ = _respond(
        _request(
            fields,
            phase="awaiting_answer",
            active_field_id="occupancy_start_date",
            event={
                "type": "message",
                "content": "Please make that even simpler.",
            },
        )
    )

    assert frustrated.effect.effect == "none"
    assert frustrated.conversation_state.phase == "awaiting_answer"
    assert "understand" in frustrated.assistant_message.casefold()
    assert "start living" in frustrated.assistant_message.casefold()
    assert simpler.effect.effect == "none"
    assert simpler.conversation_state.phase == "awaiting_answer"
    assert "start living" in simpler.assistant_message.casefold()
    assert nemotron.calls == []


def test_remembered_candidates_are_bounded_and_schema_validated() -> None:
    fields = [_field(f"field_{index}", f"Field {index}") for index in range(6)]
    candidates = [
        {
            "field_id": f"field_{index}",
            "original_value": f"value {index}",
            "value": f"value {index}",
        }
        for index in range(6)
    ]
    with pytest.raises(ValidationError):
        _request(
            fields,
            phase="asking",
            event={"type": "advance"},
            remembered_candidates=candidates,
        )

    with pytest.raises(ValidationError, match="unanswered fields"):
        _request(
            [_field("name", "Name", status="confirmed", value="Ada")],
            phase="form_complete",
            event={"type": "message", "content": "Review"},
            remembered_candidates=[
                {
                    "field_id": "name",
                    "original_value": "Ada",
                    "value": "Ada",
                }
            ],
        )
