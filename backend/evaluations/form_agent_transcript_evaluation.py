"""Deterministic complete-conversation evaluation for the Form Agent.

Each fixture checks a bounded representative set of fields through
``form_complete``. Turns-per-confirmed-field counts every action tied to that
field from the first question through confirmation. Repeated-question rate
counts clarification re-prompts after a field has already been asked.
Clarification, invalid-action, invalid-proposal, and confirmation-boundary rates
use all scheduled turns as the denominator. Live-only metrics are populated
only when a real service is passed.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json
from time import perf_counter
from typing import Any, Callable, Optional, Union, cast

from app.services.form_agent import (
    ConfirmedAction,
    ConversationState,
    FormAgentError,
    FormAgentField,
    FormAgentFormContext,
    FormAgentMessage,
    FormAgentRequest,
    FormAgentService,
    ProposeAction,
    RejectedAction,
    SkipAction,
)
from app.services.form_agent.answer_adapters import (
    AnswerAdapterResult,
    MatchedAnswer,
    NotApplicable,
)
from app.services.form_agent.value_normalizer import infer_unambiguous_answer
from app.services.nemotron_service import (
    NemotronConfigurationError,
    NemotronService,
    NemotronServiceError,
)
from app.services.pdf_service import extract_acroform
from evaluations.form_agent_evaluation import (
    FIXTURES_PATH,
    agent_field_from_pdf,
)


FieldValue = Union[str, bool]
_SAME_ACTIVE_FIELD = object()


@dataclass(frozen=True)
class TranscriptTurn:
    name: str
    event: dict[str, Any]
    expected_action: str
    expected_phase: str
    expected_action_field_id: Optional[str]
    expected_state_active_field_id: Optional[str]
    expected_confirmed_values: tuple[tuple[str, FieldValue], ...] = ()
    expected_skipped_field_ids: tuple[str, ...] = ()
    expected_value: Optional[FieldValue] = None
    expected_pending_field_id: Optional[str] = None
    expected_pending_value: Optional[FieldValue] = None
    model_response: Optional[str] = None
    expected_model_calls: int = 0
    purpose_safety_check: bool = False


@dataclass(frozen=True)
class TranscriptFixture:
    name: str
    fixture: str
    field_ids: tuple[str, ...]
    turns: tuple[TranscriptTurn, ...]


@dataclass(frozen=True)
class TranscriptEvaluationMetrics:
    total_transcripts: int
    total_turns: int
    fixture_count: int
    form_completion_rate: float
    first_attempt_accepted_proposal_rate: float
    average_turns_per_confirmed_field: float
    repeated_question_rate: float
    clarification_rate: float
    invalid_action_rate: float
    invalid_proposal_rate: float
    confirmation_boundary_failure_rate: float
    invented_fact_failures: int
    invented_purpose_failures: int
    total_model_calls: Optional[int]
    average_model_latency_ms: Optional[float]
    model_calls_per_field: Optional[float]


@dataclass(frozen=True)
class TranscriptEvaluationReport:
    metrics: TranscriptEvaluationMetrics
    failures: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "metrics": asdict(self.metrics),
            "failures": list(self.failures),
        }


@dataclass(frozen=True)
class AdapterComparisonMetrics:
    repeated_question_rate_before: float
    repeated_question_rate_after: float
    invalid_proposal_rate_before: float
    invalid_proposal_rate_after: float
    invention_failures_before: int
    invention_failures_after: int
    legacy_failure_count: int
    adapter_failure_count: int


class _TurnNemotronService:
    def __init__(
        self,
        scripted_response: Optional[str],
        live_service: Optional[NemotronService],
    ) -> None:
        self._scripted_response = scripted_response
        self._live_service = live_service
        self.call_count = 0
        self.latencies_ms: list[float] = []

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 600,
        json_response: bool = False,
    ) -> str:
        self.call_count += 1
        started_at = perf_counter()
        try:
            if self._live_service is not None:
                return await self._live_service.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    json_response=json_response,
                )
            if self._scripted_response is None:
                raise NemotronServiceError(
                    "Transcript made an unexpected model call"
                )
            return self._scripted_response
        finally:
            self.latencies_ms.append((perf_counter() - started_at) * 1000)


def transcript_fixtures() -> tuple[TranscriptFixture, ...]:
    sample_name = (("full_name", "Ada Lovelace"),)
    sample_name_country = (
        ("full_name", "Ada Lovelace"),
        ("country", "United Kingdom"),
    )
    household_name = (("applicant_full_legal_name", "Sam Example-Smith"),)
    household_name_category = (
        ("applicant_full_legal_name", "Sam Example-Smith"),
        ("primary_support_category", "Housing stability"),
    )
    household_all = household_name_category + (
        ("shares_food_or_living_costs", True),
    )
    i9_name = (("Last Name (Family Name)", "Example"),)
    i9_name_state = i9_name + (("State", "CA"),)
    sba_label = (("Monthly rent expense 1", "Monthly rent"),)
    sba_label_actual = sba_label + (
        ("Monthly actual cost 1", "1050.50"),
    )

    return (
        TranscriptFixture(
            name="sample-reject-correct-confirm-skip",
            fixture="sample_form.pdf",
            field_ids=("full_name", "country", "accept_terms"),
            turns=(
                _turn("ask-name", _advance(), "next", "awaiting_answer", "full_name"),
                _turn(
                    "unclear-name",
                    _message("What name format should I use?"),
                    "clarify",
                    "awaiting_clarification",
                    "full_name",
                    model_response=_action_json(
                        "clarify",
                        "Please provide the exact full name to enter.",
                        "full_name",
                    ),
                    expected_model_calls=1,
                ),
                _turn(
                    "first-name-proposal",
                    _message("My full name is Ada Example."),
                    "propose",
                    "awaiting_confirmation",
                    "full_name",
                    expected_value="Ada Example",
                    expected_pending_field_id="full_name",
                    expected_pending_value="Ada Example",
                    model_response=_proposal_json(
                        "full_name",
                        "same as above",
                    ),
                ),
                _turn(
                    "reject-name",
                    {"type": "reject"},
                    "rejected",
                    "awaiting_answer",
                    "full_name",
                ),
                _turn(
                    "corrected-name-proposal",
                    _message("Use Ada Lovelace instead."),
                    "propose",
                    "awaiting_confirmation",
                    "full_name",
                    expected_value="Ada Lovelace",
                    expected_pending_field_id="full_name",
                    expected_pending_value="Ada Lovelace",
                    model_response=_proposal_json("full_name", "Ada Lovelace"),
                ),
                _turn(
                    "confirm-name",
                    {"type": "confirm"},
                    "confirmed",
                    "awaiting_answer",
                    "full_name",
                    state_active_field_id="country",
                    confirmed=sample_name,
                    expected_value="Ada Lovelace",
                ),
                _turn(
                    "country-proposal",
                    _message("United Kingdom"),
                    "propose",
                    "awaiting_confirmation",
                    "country",
                    confirmed=sample_name,
                    expected_value="United Kingdom",
                    expected_pending_field_id="country",
                    expected_pending_value="United Kingdom",
                ),
                _turn(
                    "confirm-country",
                    {"type": "confirm"},
                    "confirmed",
                    "awaiting_answer",
                    "country",
                    state_active_field_id="accept_terms",
                    confirmed=sample_name_country,
                    expected_value="United Kingdom",
                ),
                _turn(
                    "skip-terms",
                    {"type": "skip", "field_id": "accept_terms"},
                    "skip",
                    "form_complete",
                    "accept_terms",
                    state_active_field_id=None,
                    confirmed=sample_name_country,
                    skipped=("accept_terms",),
                ),
            ),
        ),
        TranscriptFixture(
            name="household-clarify-and-confirm",
            fixture="household_support_review_demo.pdf",
            field_ids=(
                "applicant_full_legal_name",
                "primary_support_category",
                "shares_food_or_living_costs",
            ),
            turns=(
                _turn(
                    "ask-name",
                    _advance(),
                    "next",
                    "awaiting_answer",
                    "applicant_full_legal_name",
                ),
                _turn(
                    "name-proposal",
                    _message("My legal name is Sam Example."),
                    "propose",
                    "awaiting_confirmation",
                    "applicant_full_legal_name",
                    expected_value="Sam Example",
                    expected_pending_field_id="applicant_full_legal_name",
                    expected_pending_value="Sam Example",
                    model_response=_proposal_json(
                        "applicant_full_legal_name",
                        "Sam Example",
                    ),
                ),
                _turn(
                    "confirm-name",
                    {"type": "confirm_edit", "value": "Sam Example-Smith"},
                    "confirmed",
                    "awaiting_answer",
                    "applicant_full_legal_name",
                    state_active_field_id="primary_support_category",
                    confirmed=household_name,
                    expected_value="Sam Example-Smith",
                ),
                _turn(
                    "category-proposal",
                    _message("Housing stability"),
                    "propose",
                    "awaiting_confirmation",
                    "primary_support_category",
                    confirmed=household_name,
                    expected_value="Housing stability",
                    expected_pending_field_id="primary_support_category",
                    expected_pending_value="Housing stability",
                ),
                _turn(
                    "confirm-category",
                    {"type": "confirm"},
                    "confirmed",
                    "awaiting_answer",
                    "primary_support_category",
                    state_active_field_id="shares_food_or_living_costs",
                    confirmed=household_name_category,
                    expected_value="Housing stability",
                ),
                _turn(
                    "unclear-cost-sharing",
                    _message("Sometimes, depending on the week."),
                    "clarify",
                    "awaiting_clarification",
                    "shares_food_or_living_costs",
                    confirmed=household_name_category,
                    model_response=_action_json(
                        "clarify",
                        "Please answer yes or no for this checkbox.",
                        "shares_food_or_living_costs",
                    ),
                ),
                _turn(
                    "cost-sharing-proposal",
                    _message("Yes, I do."),
                    "propose",
                    "awaiting_confirmation",
                    "shares_food_or_living_costs",
                    confirmed=household_name_category,
                    expected_value=True,
                    expected_pending_field_id="shares_food_or_living_costs",
                    expected_pending_value=True,
                ),
                _turn(
                    "confirm-cost-sharing",
                    {"type": "confirm"},
                    "confirmed",
                    "form_complete",
                    "shares_food_or_living_costs",
                    state_active_field_id=None,
                    confirmed=household_all,
                    expected_value=True,
                ),
            ),
        ),
        TranscriptFixture(
            name="uscis-purpose-grounding-and-skip",
            fixture="real_world/uscis_i9_2025.pdf",
            field_ids=("Last Name (Family Name)", "State", "CB_1"),
            turns=(
                _turn(
                    "ask-family-name",
                    _advance(),
                    "next",
                    "awaiting_answer",
                    "Last Name (Family Name)",
                ),
                _turn(
                    "ask-purpose",
                    _message("Why does the organisation require this?"),
                    "explain",
                    "awaiting_answer",
                    "Last Name (Family Name)",
                    purpose_safety_check=True,
                ),
                _turn(
                    "family-name-proposal",
                    _message("My family name is Example."),
                    "propose",
                    "awaiting_confirmation",
                    "Last Name (Family Name)",
                    expected_value="Example",
                    expected_pending_field_id="Last Name (Family Name)",
                    expected_pending_value="Example",
                    model_response=_proposal_json(
                        "Last Name (Family Name)",
                        "Example",
                    ),
                ),
                _turn(
                    "confirm-family-name",
                    {"type": "confirm"},
                    "confirmed",
                    "awaiting_answer",
                    "Last Name (Family Name)",
                    state_active_field_id="State",
                    confirmed=i9_name,
                    expected_value="Example",
                ),
                _turn(
                    "state-proposal",
                    _message("CA"),
                    "propose",
                    "awaiting_confirmation",
                    "State",
                    confirmed=i9_name,
                    expected_value="CA",
                    expected_pending_field_id="State",
                    expected_pending_value="CA",
                ),
                _turn(
                    "confirm-state",
                    {"type": "confirm"},
                    "confirmed",
                    "awaiting_answer",
                    "State",
                    state_active_field_id="CB_1",
                    confirmed=i9_name_state,
                    expected_value="CA",
                ),
                _turn(
                    "skip-attestation",
                    {"type": "skip", "field_id": "CB_1"},
                    "skip",
                    "form_complete",
                    "CB_1",
                    state_active_field_id=None,
                    confirmed=i9_name_state,
                    skipped=("CB_1",),
                ),
            ),
        ),
        TranscriptFixture(
            name="sba-number-clarification-and-skip",
            fixture="real_world/sba_startup_costs_2023.pdf",
            field_ids=(
                "Monthly rent expense 1",
                "Monthly actual cost 1",
                "One-time budget cost 1",
            ),
            turns=(
                _turn(
                    "ask-label",
                    _advance(),
                    "next",
                    "awaiting_answer",
                    "Monthly rent expense 1",
                ),
                _turn(
                    "label-proposal",
                    _message("Keep the label as Monthly rent."),
                    "propose",
                    "awaiting_confirmation",
                    "Monthly rent expense 1",
                    expected_value="Monthly rent",
                    expected_pending_field_id="Monthly rent expense 1",
                    expected_pending_value="Monthly rent",
                    model_response=_proposal_json(
                        "Monthly rent expense 1",
                        "Monthly rent",
                    ),
                ),
                _turn(
                    "confirm-label",
                    {"type": "confirm"},
                    "confirmed",
                    "awaiting_answer",
                    "Monthly rent expense 1",
                    state_active_field_id="Monthly actual cost 1",
                    confirmed=sba_label,
                    expected_value="Monthly rent",
                ),
                _turn(
                    "unclear-actual-cost",
                    _message("It was around a thousand."),
                    "clarify",
                    "awaiting_clarification",
                    "Monthly actual cost 1",
                    confirmed=sba_label,
                    model_response=_action_json(
                        "clarify",
                        "Please provide one exact numeric amount.",
                        "Monthly actual cost 1",
                    ),
                ),
                _turn(
                    "actual-cost-proposal",
                    _message("The exact amount was £1,050.50."),
                    "propose",
                    "awaiting_confirmation",
                    "Monthly actual cost 1",
                    confirmed=sba_label,
                    expected_value="1050.50",
                    expected_pending_field_id="Monthly actual cost 1",
                    expected_pending_value="1050.50",
                ),
                _turn(
                    "confirm-actual-cost",
                    {"type": "confirm"},
                    "confirmed",
                    "awaiting_answer",
                    "Monthly actual cost 1",
                    state_active_field_id="One-time budget cost 1",
                    confirmed=sba_label_actual,
                    expected_value="1050.50",
                ),
                _turn(
                    "skip-one-time-budget",
                    {
                        "type": "skip",
                        "field_id": "One-time budget cost 1",
                    },
                    "skip",
                    "form_complete",
                    "One-time budget cost 1",
                    state_active_field_id=None,
                    confirmed=sba_label_actual,
                    skipped=("One-time budget cost 1",),
                ),
            ),
        ),
    )


async def run_transcript_evaluation(
    live_service: Optional[NemotronService] = None,
    transcripts: Optional[tuple[TranscriptFixture, ...]] = None,
    answer_interpreter: Optional[
        Callable[[FormAgentField, str], AnswerAdapterResult]
    ] = None,
    enforce_expected_model_calls: bool = True,
) -> TranscriptEvaluationReport:
    selected_transcripts = transcripts or transcript_fixtures()
    failures: list[str] = []
    completed_transcripts = 0
    clarification_count = 0
    invalid_action_count = 0
    invalid_proposal_count = 0
    confirmation_boundary_failures = 0
    invented_fact_failures = 0
    invented_purpose_failures = 0
    repeated_questions = 0
    question_count = 0
    confirmed_field_turn_counts: list[int] = []
    confirmed_fields = 0
    first_attempt_accepted_proposals = 0
    total_model_calls = 0
    model_latencies_ms: list[float] = []
    total_evaluated_fields = 0
    total_turns = sum(
        len(transcript.turns) for transcript in selected_transcripts
    )

    for transcript in selected_transcripts:
        form_context, fields = _load_transcript_fields(transcript)
        total_evaluated_fields += len(fields)
        state = ConversationState(
            phase="asking",
            active_field_id=None,
            pending_proposal=None,
        )
        history: list[FormAgentMessage] = []
        proposal_counts: dict[str, int] = {}
        rejected_fields: set[str] = set()
        field_turn_counts: dict[str, int] = {}
        previous_question_by_field: dict[str, str] = {}

        for turn_number, turn in enumerate(transcript.turns, start=1):
            turn_service = _TurnNemotronService(
                turn.model_response,
                live_service,
            )
            request = FormAgentRequest(
                form_context=form_context,
                fields=fields,
                conversation_state=state,
                event=turn.event,
                history=history[-8:],
            )

            try:
                service = FormAgentService(  # type: ignore[arg-type]
                    turn_service,
                    **(
                        {"answer_interpreter": answer_interpreter}
                        if answer_interpreter is not None
                        else {}
                    ),
                )
                response = await service.respond(request)
            except (FormAgentError, NemotronServiceError) as error:
                invalid_action_count += 1
                invalid_proposal_count += int(
                    turn.expected_action == "propose"
                )
                failures.append(
                    _failure(transcript, turn_number, turn, str(error))
                )
                total_model_calls += turn_service.call_count
                model_latencies_ms.extend(turn_service.latencies_ms)
                break

            total_model_calls += turn_service.call_count
            model_latencies_ms.extend(turn_service.latencies_ms)
            action = response.action
            action_field_id = action.field_id

            if enforce_expected_model_calls and live_service is None and (
                turn_service.call_count != turn.expected_model_calls
            ):
                failures.append(
                    _failure(
                        transcript,
                        turn_number,
                        turn,
                        "expected "
                        f"{turn.expected_model_calls} model call(s), got "
                        f"{turn_service.call_count}",
                    )
                )

            action_invalid = False
            if action.action != turn.expected_action:
                action_invalid = True
                failures.append(
                    _failure(
                        transcript,
                        turn_number,
                        turn,
                        f'expected action "{turn.expected_action}", got '
                        f'"{action.action}"',
                    )
                )
            if action_field_id != turn.expected_action_field_id:
                action_invalid = True
                failures.append(
                    _failure(
                        transcript,
                        turn_number,
                        turn,
                        "expected action field "
                        f'"{turn.expected_action_field_id}", got '
                        f'"{action_field_id}"',
                    )
                )
            invalid_action_count += int(action_invalid)
            invalid_proposal_count += int(
                turn.expected_action == "propose"
                and action.action != "propose"
            )

            action_value = getattr(action, "value", None)
            if turn.expected_value is not None and (
                action_value != turn.expected_value
            ):
                if action_value is not None:
                    invented_fact_failures += 1
                failures.append(
                    _failure(
                        transcript,
                        turn_number,
                        turn,
                        f"expected value {turn.expected_value!r}, got "
                        f"{action_value!r}",
                    )
                )
            elif isinstance(action, ProposeAction) and (
                turn.expected_value is None
            ):
                invented_fact_failures += 1
                failures.append(
                    _failure(
                        transcript,
                        turn_number,
                        turn,
                        "agent proposed a factual value when none was expected",
                    )
                )

            event_type = turn.event.get("type")
            if isinstance(action, ConfirmedAction) and event_type not in {
                "confirm",
                "confirm_edit",
            }:
                confirmation_boundary_failures += 1
                failures.append(
                    _failure(
                        transcript,
                        turn_number,
                        turn,
                        "a value was confirmed without an explicit "
                        "confirmation event",
                    )
                )
            if isinstance(action, ProposeAction):
                proposal_counts[action.field_id] = (
                    proposal_counts.get(action.field_id, 0) + 1
                )
                if (
                    response.conversation_state.phase
                    != "awaiting_confirmation"
                    or response.conversation_state.pending_proposal is None
                ):
                    confirmation_boundary_failures += 1
                    failures.append(
                        _failure(
                            transcript,
                            turn_number,
                            turn,
                            "proposal did not enter a valid pending-"
                            "confirmation state",
                        )
                    )
            if isinstance(action, RejectedAction):
                rejected_fields.add(action.field_id)

            if action_field_id is not None:
                field_turn_counts[action_field_id] = (
                    field_turn_counts.get(action_field_id, 0) + 1
                )

            if isinstance(action, ConfirmedAction):
                field = _field_by_id(fields, action.field_id)
                if field.status != "unanswered":
                    confirmation_boundary_failures += 1
                    failures.append(
                        _failure(
                            transcript,
                            turn_number,
                            turn,
                            "confirmation attempted to overwrite a resolved "
                            "field",
                        )
                    )
                fields = _replace_field(
                    fields,
                    field.model_copy(
                        update={
                            "status": "confirmed",
                            "confirmed_value": action.value,
                        }
                    ),
                )
                confirmed_fields += 1
                confirmed_field_turn_counts.append(
                    field_turn_counts[action.field_id]
                )
                if (
                    proposal_counts.get(action.field_id) == 1
                    and action.field_id not in rejected_fields
                ):
                    first_attempt_accepted_proposals += 1
            elif isinstance(action, SkipAction):
                field = _field_by_id(fields, action.field_id)
                fields = _replace_field(
                    fields,
                    field.model_copy(
                        update={"status": "skipped", "confirmed_value": None}
                    ),
                )

            state = response.conversation_state
            clarification_count += int(action.action == "clarify")
            progressed_field_id = (
                state.active_field_id
                if isinstance(action, (ConfirmedAction, SkipAction))
                and state.phase == "awaiting_answer"
                else None
            )
            if progressed_field_id is not None:
                field_turn_counts[progressed_field_id] = (
                    field_turn_counts.get(progressed_field_id, 0) + 1
                )
                question_count += 1
                previous_question_by_field[progressed_field_id] = " ".join(
                    action.message.casefold().split()
                )
            elif action.action in {"next", "clarify"} and (
                action_field_id is not None
            ):
                question_count += 1
                normalized_question = " ".join(
                    action.message.casefold().split()
                )
                if (
                    action.action == "clarify"
                    and action_field_id in previous_question_by_field
                ):
                    repeated_questions += 1
                previous_question_by_field[action_field_id] = normalized_question

            if turn.purpose_safety_check:
                normalized_message = action.message.casefold()
                if not (
                    "authoritative reason" in normalized_message
                    and "official instructions" in normalized_message
                ):
                    invented_purpose_failures += 1
                    failures.append(
                        _failure(
                            transcript,
                            turn_number,
                            turn,
                            "purpose response was not grounded in available "
                            "official context",
                        )
                    )

            _append_history(history, turn.event, action.message)
            _assert_turn_state(
                transcript,
                turn_number,
                turn,
                state,
                fields,
                failures,
            )

        if state.phase == "form_complete" and all(
            field.status != "unanswered" for field in fields
        ):
            completed_transcripts += 1
        else:
            final_turn_number = len(transcript.turns)
            final_turn = transcript.turns[-1]
            failures.append(
                _failure(
                    transcript,
                    final_turn_number,
                    final_turn,
                    "transcript did not reach form_complete with every "
                    "evaluated field reviewed",
                )
            )

    is_live = live_service is not None
    metrics = TranscriptEvaluationMetrics(
        total_transcripts=len(selected_transcripts),
        total_turns=total_turns,
        fixture_count=len(
            {transcript.fixture for transcript in selected_transcripts}
        ),
        form_completion_rate=_rate(
            completed_transcripts,
            len(selected_transcripts),
        ),
        first_attempt_accepted_proposal_rate=_rate(
            first_attempt_accepted_proposals,
            confirmed_fields,
        ),
        average_turns_per_confirmed_field=_average(
            confirmed_field_turn_counts
        ),
        repeated_question_rate=_rate(repeated_questions, question_count),
        clarification_rate=_rate(clarification_count, total_turns),
        invalid_action_rate=_rate(invalid_action_count, total_turns),
        invalid_proposal_rate=_rate(invalid_proposal_count, total_turns),
        confirmation_boundary_failure_rate=_rate(
            confirmation_boundary_failures,
            total_turns,
        ),
        invented_fact_failures=invented_fact_failures,
        invented_purpose_failures=invented_purpose_failures,
        total_model_calls=total_model_calls if is_live else None,
        average_model_latency_ms=(
            round(_average(model_latencies_ms), 3) if is_live else None
        ),
        model_calls_per_field=(
            round(total_model_calls / total_evaluated_fields, 3)
            if is_live and total_evaluated_fields
            else None
        ),
    )
    return TranscriptEvaluationReport(
        metrics=metrics,
        failures=tuple(failures),
    )


async def run_adapter_comparison(
    transcripts: Optional[tuple[TranscriptFixture, ...]] = None,
) -> AdapterComparisonMetrics:
    selected_transcripts = transcripts or transcript_fixtures()
    adapter_report = await run_transcript_evaluation(
        transcripts=selected_transcripts,
    )
    legacy_report = await run_transcript_evaluation(
        transcripts=selected_transcripts,
        answer_interpreter=_legacy_answer_interpreter,
        enforce_expected_model_calls=False,
    )
    before = legacy_report.metrics
    after = adapter_report.metrics
    return AdapterComparisonMetrics(
        repeated_question_rate_before=before.repeated_question_rate,
        repeated_question_rate_after=after.repeated_question_rate,
        invalid_proposal_rate_before=before.invalid_proposal_rate,
        invalid_proposal_rate_after=after.invalid_proposal_rate,
        invention_failures_before=(
            before.invented_fact_failures + before.invented_purpose_failures
        ),
        invention_failures_after=(
            after.invented_fact_failures + after.invented_purpose_failures
        ),
        legacy_failure_count=len(legacy_report.failures),
        adapter_failure_count=len(adapter_report.failures),
    )


def _turn(
    name: str,
    event: dict[str, Any],
    expected_action: str,
    expected_phase: str,
    expected_action_field_id: Optional[str],
    *,
    state_active_field_id: object = _SAME_ACTIVE_FIELD,
    confirmed: tuple[tuple[str, FieldValue], ...] = (),
    skipped: tuple[str, ...] = (),
    expected_value: Optional[FieldValue] = None,
    expected_pending_field_id: Optional[str] = None,
    expected_pending_value: Optional[FieldValue] = None,
    model_response: Optional[str] = None,
    expected_model_calls: int = 0,
    purpose_safety_check: bool = False,
) -> TranscriptTurn:
    return TranscriptTurn(
        name=name,
        event=event,
        expected_action=expected_action,
        expected_phase=expected_phase,
        expected_action_field_id=expected_action_field_id,
        expected_state_active_field_id=(
            expected_action_field_id
            if state_active_field_id is _SAME_ACTIVE_FIELD
            else cast(Optional[str], state_active_field_id)
        ),
        expected_confirmed_values=confirmed,
        expected_skipped_field_ids=skipped,
        expected_value=expected_value,
        expected_pending_field_id=expected_pending_field_id,
        expected_pending_value=expected_pending_value,
        model_response=model_response,
        expected_model_calls=expected_model_calls,
        purpose_safety_check=purpose_safety_check,
    )


def _advance() -> dict[str, str]:
    return {"type": "advance"}


def _message(content: str) -> dict[str, str]:
    return {"type": "message", "content": content}


def _proposal_json(field_id: str, value: FieldValue) -> str:
    return json.dumps(
        {
            "action": "propose",
            "message": "Proposal awaiting confirmation.",
            "field_id": field_id,
            "value": value,
        }
    )


def _action_json(action: str, message: str, field_id: str) -> str:
    return json.dumps(
        {"action": action, "message": message, "field_id": field_id}
    )


def _legacy_answer_interpreter(
    field: FormAgentField,
    message: str,
) -> AnswerAdapterResult:
    value = infer_unambiguous_answer(field.type, field.options, message)
    if value is None:
        return NotApplicable()
    return MatchedAnswer(value)


def _load_transcript_fields(
    transcript: TranscriptFixture,
) -> tuple[FormAgentFormContext, list[FormAgentField]]:
    extraction = extract_acroform(
        (FIXTURES_PATH / transcript.fixture).read_bytes()
    )
    extracted_by_id = {field.id: field for field in extraction.fields}
    fields = []
    for field_id in transcript.field_ids:
        pdf_field = extracted_by_id.get(field_id)
        if pdf_field is None:
            raise ValueError(
                f'{transcript.name}: fixture is missing field "{field_id}"'
            )
        agent_field = agent_field_from_pdf(pdf_field)
        if agent_field is None:
            raise ValueError(
                f'{transcript.name}: field "{field_id}" is unsupported'
            )
        fields.append(agent_field)

    return (
        FormAgentFormContext(
            title=extraction.form_context.title,
            instructions=list(extraction.form_context.instructions),
        ),
        fields,
    )


def _replace_field(
    fields: list[FormAgentField],
    replacement: FormAgentField,
) -> list[FormAgentField]:
    return [
        replacement if field.id == replacement.id else field
        for field in fields
    ]


def _field_by_id(
    fields: list[FormAgentField],
    field_id: str,
) -> FormAgentField:
    return next(field for field in fields if field.id == field_id)


def _append_history(
    history: list[FormAgentMessage],
    event: dict[str, Any],
    assistant_message: str,
) -> None:
    content = event.get("content")
    if isinstance(content, str):
        history.append(FormAgentMessage(role="user", content=content))
    history.append(
        FormAgentMessage(role="assistant", content=assistant_message)
    )


def _assert_turn_state(
    transcript: TranscriptFixture,
    turn_number: int,
    turn: TranscriptTurn,
    state: ConversationState,
    fields: list[FormAgentField],
    failures: list[str],
) -> None:
    if state.phase != turn.expected_phase:
        failures.append(
            _failure(
                transcript,
                turn_number,
                turn,
                f'expected phase "{turn.expected_phase}", got '
                f'"{state.phase}"',
            )
        )
    if state.active_field_id != turn.expected_state_active_field_id:
        failures.append(
            _failure(
                transcript,
                turn_number,
                turn,
                "expected active field "
                f'"{turn.expected_state_active_field_id}", got '
                f'"{state.active_field_id}"',
            )
        )

    pending = state.pending_proposal
    actual_pending_field_id = pending.field_id if pending else None
    actual_pending_value = pending.value if pending else None
    if (
        actual_pending_field_id != turn.expected_pending_field_id
        or actual_pending_value != turn.expected_pending_value
    ):
        failures.append(
            _failure(
                transcript,
                turn_number,
                turn,
                "pending proposal did not match the expected field and value",
            )
        )

    actual_confirmed = tuple(
        (field.id, field.confirmed_value)
        for field in fields
        if field.status == "confirmed" and field.confirmed_value is not None
    )
    if actual_confirmed != turn.expected_confirmed_values:
        failures.append(
            _failure(
                transcript,
                turn_number,
                turn,
                f"expected confirmed values {turn.expected_confirmed_values!r}, "
                f"got {actual_confirmed!r}",
            )
        )

    actual_skipped = tuple(
        field.id for field in fields if field.status == "skipped"
    )
    if actual_skipped != turn.expected_skipped_field_ids:
        failures.append(
            _failure(
                transcript,
                turn_number,
                turn,
                f"expected skipped fields {turn.expected_skipped_field_ids!r}, "
                f"got {actual_skipped!r}",
            )
        )


def _failure(
    transcript: TranscriptFixture,
    turn_number: int,
    turn: TranscriptTurn,
    message: str,
) -> str:
    return f"{transcript.name}, turn {turn_number} ({turn.name}): {message}"


def _rate(successes: int, checks: int) -> float:
    return round(successes / checks, 3) if checks else 1.0


def _average(values: list[int] | list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


async def _run_cli(live: bool) -> int:
    live_service = None
    if live:
        try:
            live_service = NemotronService.from_environment()
        except NemotronConfigurationError as error:
            print(str(error))
            return 2

    report = await run_transcript_evaluation(live_service=live_service)
    output = report.as_dict()
    if not live:
        comparison = await run_adapter_comparison()
        output["adapter_comparison"] = asdict(comparison)
    print(json.dumps(output, indent=2))
    return 0 if not report.failures else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate complete Form Agent conversations across supported "
            "PDF fixtures."
        )
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call Nemotron using the configured Nebius environment variables.",
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(_run_cli(arguments.live)))


if __name__ == "__main__":
    main()
