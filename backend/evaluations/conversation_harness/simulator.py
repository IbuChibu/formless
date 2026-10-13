from __future__ import annotations

from time import perf_counter
from typing import Optional

from app.services.form_agent import (
    ConversationState,
    FormAgentField,
    FormAgentFormContext,
    FormAgentMessage,
    FormAgentRequest,
)
from app.services.pdf_service import extract_acroform
from evaluations.form_agent_evaluation import FIXTURES_PATH, agent_field_from_pdf

from .models import (
    ConversationScenario,
    Persona,
    RecordedTurn,
    ScenarioReport,
)
from .scoring import score_scenario
from .targets import ConversationTarget


class ConversationSimulator:
    """Drive the public Form Agent contract while mirroring frontend state effects."""

    def __init__(self, target: ConversationTarget) -> None:
        self._target = target

    async def run(
        self,
        scenario: ConversationScenario,
        persona: Persona,
    ) -> ScenarioReport:
        form_context, fields = _load_scenario_fields(scenario)
        state = _initial_state(fields)
        history: list[FormAgentMessage] = []
        transcript: list[RecordedTurn] = []

        for index, turn in enumerate(scenario.turns, start=1):
            event = dict(turn.event)
            visible_user_message = turn.visible_user_message
            if visible_user_message is None and event.get("type") == "message":
                content = event.get("content")
                visible_user_message = content if isinstance(content, str) else None

            request = FormAgentRequest.model_validate(
                {
                    "form_context": form_context.model_dump(mode="json"),
                    "fields": [field.model_dump(mode="json") for field in fields],
                    "conversation_state": state.model_dump(mode="json"),
                    "event": event,
                    "history": [
                        message.model_dump(mode="json") for message in history[-8:]
                    ],
                }
            )
            fields_before = _field_state(fields)
            started_at = perf_counter()
            try:
                response = await self._target.respond(request)
            # The artifact must retain provider/API failures.
            except Exception as error:
                transcript.append(
                    RecordedTurn(
                        id=turn.id,
                        index=index,
                        tags=list(turn.tags),
                        user_event=event,
                        visible_user_message=visible_user_message,
                        request_state=state.model_dump(mode="json"),
                        fields_before=fields_before,
                        fields_after=fields_before,
                        latency_ms=round(
                            (perf_counter() - started_at) * 1000,
                            3,
                        ),
                        expectation_failures=[
                            "The application interface did not return a response"
                        ],
                        error=f"{error.__class__.__name__}: {error}",
                    )
                )
                break

            latency_ms = round((perf_counter() - started_at) * 1000, 3)
            expectation_failures = _check_turn_expectation(
                turn.expect,
                request.conversation_state,
                response.effect.model_dump(mode="json"),
                response.conversation_state.model_dump(mode="json"),
                response.assistant_message,
            )
            fields = _apply_effect(fields, response.effect.model_dump(mode="json"))
            state = response.conversation_state
            fields_after = _field_state(fields)

            transcript.append(
                RecordedTurn(
                    id=turn.id,
                    index=index,
                    tags=list(turn.tags),
                    user_event=event,
                    visible_user_message=visible_user_message,
                    request_state=request.conversation_state.model_dump(mode="json"),
                    fields_before=fields_before,
                    assistant_message=response.assistant_message,
                    response_effect=response.effect.model_dump(mode="json"),
                    response_state=response.conversation_state.model_dump(
                        mode="json"
                    ),
                    fields_after=fields_after,
                    latency_ms=latency_ms,
                    expectation_failures=expectation_failures,
                )
            )

            if visible_user_message:
                history.append(
                    FormAgentMessage(role="user", content=visible_user_message)
                )
            history.append(
                FormAgentMessage(
                    role="assistant",
                    content=response.assistant_message,
                )
            )

        actual_state = _field_state(fields)
        scores, failures = score_scenario(scenario, transcript, actual_state)
        return ScenarioReport(
            scenario_id=scenario.id,
            title=scenario.title,
            purpose=scenario.purpose,
            persona=persona,
            fixture=scenario.fixture,
            tags=list(scenario.tags),
            expected_final_state=scenario.expected_final,
            actual_form_state=actual_state,
            transcript=transcript,
            scores=scores,
            deterministic_failures=failures,
        )


def _load_scenario_fields(
    scenario: ConversationScenario,
) -> tuple[FormAgentFormContext, list[FormAgentField]]:
    fixture_path = (FIXTURES_PATH / scenario.fixture).resolve()
    fixtures_root = FIXTURES_PATH.resolve()
    if fixtures_root not in fixture_path.parents:
        raise ValueError("Scenario fixture must be inside backend/tests/fixtures")
    extraction = extract_acroform(fixture_path.read_bytes())
    available = {
        field.id: agent_field
        for field in extraction.fields
        if (agent_field := agent_field_from_pdf(field)) is not None
    }
    missing = [field_id for field_id in scenario.field_ids if field_id not in available]
    if missing:
        raise ValueError(
            f"{scenario.id} references unavailable fields: {', '.join(missing)}"
        )

    fields: list[FormAgentField] = []
    skipped = set(scenario.initial_skipped_field_ids)
    for field_id in scenario.field_ids:
        field = available[field_id]
        if field_id in scenario.initial_confirmed_values:
            field = field.model_copy(
                update={
                    "status": "confirmed",
                    "confirmed_value": scenario.initial_confirmed_values[field_id],
                }
            )
            field = FormAgentField.model_validate(field.model_dump(mode="json"))
        elif field_id in skipped:
            field = field.model_copy(update={"status": "skipped"})
        fields.append(field)

    context = FormAgentFormContext(
        title=extraction.form_context.title,
        instructions=list(extraction.form_context.instructions),
        form_id=extraction.form_context.form_id,
        form_version=extraction.form_context.form_version,
    )
    return context, fields


def _initial_state(fields: list[FormAgentField]) -> ConversationState:
    if any(field.status == "unanswered" for field in fields):
        return ConversationState(
            phase="asking",
            active_field_id=None,
            pending_proposal=None,
        )
    return ConversationState(
        phase="form_complete",
        active_field_id=None,
        pending_proposal=None,
    )


def _field_state(fields: list[FormAgentField]) -> dict[str, dict[str, object]]:
    return {
        field.id: {
            "status": field.status,
            "confirmed_value": field.confirmed_value,
        }
        for field in fields
    }


def _apply_effect(
    fields: list[FormAgentField],
    effect: dict[str, object],
) -> list[FormAgentField]:
    effect_name = effect.get("effect")
    field_id = effect.get("field_id")
    if not isinstance(field_id, str):
        return fields

    updated: list[FormAgentField] = []
    for field in fields:
        if field.id != field_id:
            updated.append(field)
            continue
        if effect_name == "confirmed":
            candidate = field.model_copy(
                update={
                    "status": "confirmed",
                    "confirmed_value": effect.get("value"),
                }
            )
            updated.append(
                FormAgentField.model_validate(candidate.model_dump(mode="json"))
            )
        elif effect_name == "skipped":
            updated.append(
                field.model_copy(update={"status": "skipped", "confirmed_value": None})
            )
        elif effect_name == "field_reopened":
            updated.append(
                field.model_copy(
                    update={"status": "unanswered", "confirmed_value": None}
                )
            )
        else:
            updated.append(field)
    return updated


def _check_turn_expectation(
    expectation: object,
    request_state: ConversationState,
    effect: dict[str, object],
    response_state: dict[str, object],
    assistant_message: str,
) -> list[str]:
    failures: list[str] = []
    expected_effects = getattr(expectation, "effects")
    if expected_effects and effect.get("effect") not in expected_effects:
        failures.append(
            f"expected effect in {expected_effects}, got {effect.get('effect')!r}"
        )
    expected_phase: Optional[str] = getattr(expectation, "phase")
    if expected_phase is not None and response_state.get("phase") != expected_phase:
        failures.append(
            f"expected phase {expected_phase!r}, got {response_state.get('phase')!r}"
        )
    expected_field_id: Optional[str] = getattr(expectation, "field_id")
    if expected_field_id is not None and effect.get("field_id") != expected_field_id:
        failures.append(
            f"expected effect field {expected_field_id!r}, got "
            f"{effect.get('field_id')!r}"
        )
    expected_value = getattr(expectation, "prepared_value")
    if expected_value is not None:
        actual_value = effect.get("prepared_value", effect.get("value"))
        if actual_value != expected_value:
            failures.append(
                f"expected prepared value {expected_value!r}, got {actual_value!r}"
            )
    if getattr(expectation, "state_unchanged") and response_state != (
        request_state.model_dump(mode="json")
    ):
        failures.append("expected the conversation state to remain unchanged")
    expected_terms: list[str] = getattr(expectation, "message_includes_any")
    if expected_terms:
        normalized_message = assistant_message.casefold()
        if not any(term.casefold() in normalized_message for term in expected_terms):
            failures.append(
                "assistant message did not include any expected term: "
                + ", ".join(expected_terms)
            )
    return failures
