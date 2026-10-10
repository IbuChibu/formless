from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

from evaluations.form_agent_transcript_evaluation import (
    run_adapter_comparison,
    run_transcript_evaluation,
    transcript_fixtures,
)


class ScriptedLiveService:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_offline_transcripts_cover_complete_multiform_conversations() -> None:
    transcripts = transcript_fixtures()
    report = asyncio.run(run_transcript_evaluation())

    assert {transcript.fixture for transcript in transcripts} == {
        "sample_form.pdf",
        "household_support_review_demo.pdf",
        "real_world/uscis_i9_2025.pdf",
        "real_world/sba_startup_costs_2023.pdf",
    }
    assert {
        turn.expected_action
        for transcript in transcripts
        for turn in transcript.turns
    } >= {
        "next",
        "clarify",
        "propose",
        "rejected",
        "confirmed",
        "skip",
    }
    assert {
        turn.event["type"]
        for transcript in transcripts
        for turn in transcript.turns
    } >= {
        "advance",
        "message",
        "reject",
        "confirm",
        "confirm_edit",
        "skip",
    }

    assert report.failures == ()
    assert report.metrics.total_transcripts == 4
    assert report.metrics.total_turns == 31
    assert report.metrics.fixture_count == 4
    assert report.metrics.form_completion_rate == 1.0
    assert report.metrics.first_attempt_accepted_proposal_rate == 0.889
    assert report.metrics.average_turns_per_confirmed_field == 3.667
    assert report.metrics.repeated_question_rate == 0.2
    assert report.metrics.clarification_rate == 0.097
    assert report.metrics.invalid_action_rate == 0.0
    assert report.metrics.invalid_proposal_rate == 0.0
    assert report.metrics.confirmation_boundary_failure_rate == 0.0
    assert report.metrics.invented_fact_failures == 0
    assert report.metrics.invented_purpose_failures == 0
    assert report.metrics.total_model_calls is None
    assert report.metrics.average_model_latency_ms is None
    assert report.metrics.model_calls_per_field is None


def test_adapter_comparison_improves_reprompts_and_invalid_proposals() -> None:
    comparison = asyncio.run(run_adapter_comparison())

    assert comparison.repeated_question_rate_before == 0.286
    assert comparison.repeated_question_rate_after == 0.2
    assert comparison.invalid_proposal_rate_before == 0.032
    assert comparison.invalid_proposal_rate_after == 0.0
    assert comparison.invention_failures_before == 0
    assert comparison.invention_failures_after == 0
    assert comparison.legacy_failure_count > 0
    assert comparison.adapter_failure_count == 0


def test_every_transcript_turn_declares_expected_state_and_field_values() -> None:
    for transcript in transcript_fixtures():
        assert transcript.turns[-1].expected_phase == "form_complete"
        for turn in transcript.turns:
            assert turn.expected_phase
            assert isinstance(turn.expected_confirmed_values, tuple)
            assert isinstance(turn.expected_skipped_field_ids, tuple)
            if turn.expected_phase == "awaiting_confirmation":
                assert turn.expected_pending_field_id is not None
                assert turn.expected_pending_value is not None
            else:
                assert turn.expected_pending_field_id is None
                assert turn.expected_pending_value is None


def test_failure_output_identifies_exact_transcript_and_turn() -> None:
    transcript = transcript_fixtures()[0]
    first_turn = replace(
        transcript.turns[0],
        expected_action="clarify",
    )
    failing_transcript = replace(
        transcript,
        name="failure-location-check",
        turns=(first_turn, *transcript.turns[1:]),
    )

    report = asyncio.run(
        run_transcript_evaluation(transcripts=(failing_transcript,))
    )

    assert report.failures[0] == (
        "failure-location-check, turn 1 (ask-name): expected action "
        '"clarify", got "next"'
    )
    assert report.metrics.invalid_action_rate == 0.111


def test_optional_live_mode_reports_latency_and_model_calls_per_field() -> None:
    transcript = transcript_fixtures()[0]
    live_service = ScriptedLiveService(
        [
            '{"action":"clarify","message":"Please provide the exact '
            'full name to enter.","field_id":"full_name"}',
            '{"action":"propose","message":"Proposal",'
            '"field_id":"full_name","value":"Ada Example"}',
            '{"action":"propose","message":"Proposal",'
            '"field_id":"full_name","value":"Ada Lovelace"}',
        ]
    )

    report = asyncio.run(
        run_transcript_evaluation(  # type: ignore[arg-type]
            live_service=live_service,
            transcripts=(transcript,),
        )
    )

    assert report.failures == ()
    assert report.metrics.total_model_calls == 1
    assert report.metrics.average_model_latency_ms is not None
    assert report.metrics.model_calls_per_field == 0.333
    assert len(live_service.calls) == 1
