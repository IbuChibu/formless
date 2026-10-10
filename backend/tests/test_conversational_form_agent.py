from __future__ import annotations

import asyncio
import json
from typing import Any

from app.services.form_agent import FormAgentRequest, FormAgentService


class StubNemotronService:
    def __init__(self, response: str | list[str] = "not used") -> None:
        self.responses = response.copy() if isinstance(response, list) else [response]
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


class StubTavilyService:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(self, query: str) -> tuple[Any, ...]:
        self.queries.append(query)
        return ()


def _request(
    message: str,
    *,
    phase: str = "awaiting_answer",
    pending_proposal: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> FormAgentRequest:
    return FormAgentRequest.model_validate(
        {
            "form_context": {
                "title": "Address history form",
                "instructions": ["Give dates as accurately as you can."],
            },
            "fields": [
                {
                    "id": "move_in_date",
                    "label": "Move-in date",
                    "question": (
                        "The date you began living at the address you "
                        "ordinarily reside at"
                    ),
                    "type": "text",
                    "status": "unanswered",
                },
                {
                    "id": "full_name",
                    "label": "Full name",
                    "type": "text",
                    "status": "confirmed",
                    "confirmed_value": "Ada Lovelace",
                },
                {
                    "id": "previous_address",
                    "label": "Previous address",
                    "type": "textarea",
                    "status": "skipped",
                },
                {
                    "id": "country",
                    "label": "Country",
                    "type": "dropdown",
                    "options": ["United Kingdom", "United States", "Other"],
                    "status": "unanswered",
                },
            ],
            "conversation_state": {
                "phase": phase,
                "active_field_id": "move_in_date",
                "pending_proposal": pending_proposal,
            },
            "event": {"type": "message", "content": message},
            "history": history or [],
        }
    )


def _respond(
    request: FormAgentRequest,
    nemotron: StubNemotronService,
    tavily: StubTavilyService,
):
    return asyncio.run(
        FormAgentService(  # type: ignore[arg-type]
            nemotron,
            tavily,  # type: ignore[arg-type]
        ).respond(request)
    )


def _prompt_context(nemotron: StubNemotronService) -> dict[str, Any]:
    raw_context = nemotron.calls[0]["user_prompt"].split(
        "UNTRUSTED_AGENT_CONTEXT\n",
        maxsplit=1,
    )[1].split("\nEND_UNTRUSTED_AGENT_CONTEXT", maxsplit=1)[0]
    return json.loads(raw_context)


def test_wording_clarification_uses_nemotron_once_without_tavily() -> None:
    request = _request("What does this mean?")
    nemotron = StubNemotronService(
        '{"action":"explain","message":"This asks when you started '
        'living at your usual or main home address. You can answer now, ask '
        'me to explain more, or skip it for now.",'
        '"field_id":"move_in_date"}'
    )
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert "usual or main home address" in response.action.message
    assert response.conversation_state == request.conversation_state
    assert response.guidance == []
    assert response.web_guidance is None
    assert len(nemotron.calls) == 1
    assert tavily.queries == []

    context = _prompt_context(nemotron)
    assert context["conversation"]["turn_objective"] == "paraphrase"
    assert context["active_field"]["id"] == "move_in_date"
    assert context["progress"] == {
        "supported": 4,
        "confirmed": 1,
        "proposed": 0,
        "skipped": 1,
        "unanswered": 2,
    }
    assert "raw_pdf" not in context
    assert "direct plain-language restatement" in (
        nemotron.calls[0]["system_prompt"]
    )


def test_pronoun_follow_up_uses_active_field_and_bounded_history() -> None:
    request = _request(
        "Explain that more simply.",
        phase="awaiting_clarification",
        history=[
            {"role": "user", "content": "What does this mean?"},
            {
                "role": "assistant",
                "content": "It asks when this became your usual address.",
            },
        ],
    )
    nemotron = StubNemotronService(
        '{"action":"explain","message":"When did you start living at '
        'the home you normally live in? You can answer, ask another '
        'question, or skip it for now.","field_id":"move_in_date"}'
    )
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert response.conversation_state == request.conversation_state
    assert len(nemotron.calls) == 1
    assert tavily.queries == []
    context = _prompt_context(nemotron)
    assert context["conversation"]["recent_history"] == request.model_dump()[
        "history"
    ]


def test_wording_clarification_cannot_become_a_field_proposal() -> None:
    request = _request("Explain that more simply.")
    nemotron = StubNemotronService(
        [
            '{"action":"propose","message":"Use this date.",'
            '"field_id":"move_in_date","value":"12 June 2019"}',
            '{"action":"explain","message":"It asks when you started '
            'living at your usual home.","field_id":"move_in_date"}',
        ]
    )
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert response.conversation_state == request.conversation_state
    assert len(nemotron.calls) == 2
    assert "requires an explanation action" in (
        nemotron.calls[1]["user_prompt"]
    )
    assert tavily.queries == []


def test_progress_question_is_deterministic_and_preserves_the_active_field() -> None:
    request = _request("What have we completed so far?")
    nemotron = StubNemotronService()
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert "confirmed 1 of 4 supported questions" in response.action.message
    assert "skipped 1" in response.action.message
    assert "2 unanswered" in response.action.message
    assert "date you began living" in response.action.message.casefold()
    assert response.conversation_state == request.conversation_state
    assert nemotron.calls == []
    assert tavily.queries == []


def test_return_later_question_is_deterministic_navigation_help() -> None:
    request = _request("Can we return to this later?")
    nemotron = StubNemotronService()
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert "skip it for now" in response.action.message
    assert response.conversation_state == request.conversation_state
    assert nemotron.calls == []
    assert tavily.queries == []


def test_progress_question_preserves_a_pending_proposal() -> None:
    pending = {"field_id": "move_in_date", "value": "12 June 2019"}
    request = _request(
        "How far are we?",
        phase="awaiting_confirmation",
        pending_proposal=pending,
    )
    nemotron = StubNemotronService()
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert "1 answer awaiting confirmation" in response.action.message
    assert response.conversation_state == request.conversation_state
    assert nemotron.calls == []
    assert tavily.queries == []


def test_wording_question_can_interrupt_and_preserve_a_pending_proposal() -> None:
    pending = {"field_id": "move_in_date", "value": "12 June 2019"}
    request = _request(
        "What does that question mean?",
        phase="awaiting_confirmation",
        pending_proposal=pending,
    )
    nemotron = StubNemotronService(
        '{"action":"explain","message":"It asks when your current home '
        'became the place you normally live. The proposed date is still '
        'waiting for your review.","field_id":"move_in_date"}'
    )
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert response.conversation_state == request.conversation_state
    assert len(nemotron.calls) == 1
    assert tavily.queries == []


def test_clear_conversational_date_becomes_a_proposal_without_services() -> None:
    request = _request("I started living there on 12 June 2019.")
    nemotron = StubNemotronService()
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "propose"
    assert response.action.value == "12 June 2019"  # type: ignore[union-attr]
    assert response.conversation_state.phase == "awaiting_confirmation"
    assert "awaiting your confirmation" in response.action.message
    assert nemotron.calls == []
    assert tavily.queries == []


def test_partial_date_gets_a_specific_clarification_without_guessing() -> None:
    request = _request("I think it was around summer 2019.")
    nemotron = StubNemotronService()
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "clarify"
    assert "You said summer 2019" in response.action.message
    assert "month and day" in response.action.message
    assert response.conversation_state.phase == "awaiting_clarification"
    assert nemotron.calls == []
    assert tavily.queries == []


def test_evidence_question_uses_tavily_but_not_nemotron_when_no_result_remains() -> None:
    request = _request("Why is this legally required?")
    nemotron = StubNemotronService()
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "explain"
    assert "won't guess" in response.action.message
    assert response.web_guidance is not None
    assert response.web_guidance.status == "empty"
    assert len(tavily.queries) == 1
    assert nemotron.calls == []


def test_acknowledgement_does_not_confirm_a_pending_proposal() -> None:
    pending = {"field_id": "move_in_date", "value": "12 June 2019"}
    request = _request(
        "Okay, that makes sense.",
        phase="awaiting_confirmation",
        pending_proposal=pending,
    )
    nemotron = StubNemotronService()
    tavily = StubTavilyService()

    response = _respond(request, nemotron, tavily)

    assert response.action.action == "clarify"
    assert response.conversation_state == request.conversation_state
    assert nemotron.calls == []
    assert tavily.queries == []
