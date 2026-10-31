from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from app.services.form_agent import FormAgentRequest, FormAgentService
from evaluations.conversation_harness.judge import (
    _JUDGE_SYSTEM_PROMPT,
    NemotronPairwiseJudge,
    NemotronQualitativeJudge,
)
from evaluations.conversation_harness.models import (
    BehaviorExpectation,
    BranchCondition,
    ConversationScenario,
    ExpectedFinalState,
    Persona,
    ScenarioSuite,
    ScenarioTurn,
    TurnExpectation,
    TurnBranch,
)
from evaluations.conversation_harness.reporting import (
    compare_suite_reports,
    load_report,
    save_suite_report,
)
from evaluations.conversation_harness.runner import run_suite
from evaluations.conversation_harness.scoring import (
    _confirmation_boundary_failures,
    _implicit_review_failures,
)
from evaluations.conversation_harness.scenarios import load_scenario_suite
from evaluations.conversation_harness.simulator import ConversationSimulator
from evaluations.conversation_harness.targets import (
    HttpConversationTarget,
    ServiceConversationTarget,
)


VOICE_RELIABILITY_SCENARIOS = (
    Path(__file__).parents[1]
    / "evaluations"
    / "scenarios"
    / "voice_interview_reliability.json"
)
HUMAN_HELPER_SCENARIOS = (
    Path(__file__).parents[1]
    / "evaluations"
    / "scenarios"
    / "human_helper_experience.json"
)
HUMAN_HELPER_V2_SCENARIOS = (
    Path(__file__).parents[1]
    / "evaluations"
    / "scenarios"
    / "human_helper_experience_v2.json"
)


class NeverCalledNemotron:
    model = "test-never-called"

    async def complete(self, **kwargs: Any) -> str:
        raise AssertionError("This deterministic scenario should not call Nemotron")


class SemanticNameNemotron:
    model = "test-semantic-name"

    async def complete(self, **kwargs: Any) -> str:
        return json.dumps(
            {
                "intent": "answer_current_field",
                "confidence": "high",
                "needs_clarification": False,
                "clarification_reason": None,
                "candidates": [
                    {
                        "field_id": "full_name",
                        "value": "Ada Example",
                        "evidence": "ada example",
                    }
                ],
                "referenced_field_id": None,
                "assistance_needs": [],
                "interaction_mode": None,
                "assistant_reply": "Ada Example — is that exactly right?",
                "decision_evidence": None,
            }
        )


class StubJudgeService:
    model = "test-judge"

    async def complete(self, **kwargs: Any) -> str:
        return json.dumps(
            {
                "naturalness": 4,
                "context_awareness": 5,
                "clarification_quality": None,
                "recovery_quality": None,
                "invents_information": False,
                "summary": "The short conversation remained grounded.",
                "failure_reasons": [],
            }
        )


class RetryJudgeService(StubJudgeService):
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, **kwargs: Any) -> str:
        self.calls += 1
        if self.calls == 1:
            return '{"naturalness": 0}'
        return await super().complete(**kwargs)


class UnsafeThenGroundedHousingJudgeService(StubJudgeService):
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, **kwargs: Any) -> str:
        self.calls += 1
        payload = json.loads(await super().complete(**kwargs))
        payload["failure_reasons"] = (
            [
                "The assistant did not explore whether living alone might "
                "indicate sole tenancy."
            ]
            if self.calls == 1
            else []
        )
        return json.dumps(payload)


class StubPairwiseJudgeService:
    model = "test-pairwise-judge"

    async def complete(self, **kwargs: Any) -> str:
        return json.dumps(
            {
                "preferred": "A",
                "attentiveness_winner": "A",
                "helpfulness_winner": "A",
                "conversational_flow_winner": "A",
                "user_effort_winner": "A",
                "safety_concern": False,
                "reason": "A responds more directly with less user effort.",
            }
        )


def _persona() -> Persona:
    return Persona(
        id="synthetic",
        name="Synthetic user",
        summary="A test-only user.",
        communication_style="Concise.",
        behaviours=["answers directly"],
    )


def _scenario() -> ConversationScenario:
    return ConversationScenario(
        id="deterministic-name",
        title="Complete one name field",
        persona_id="synthetic",
        fixture="sample_form.pdf",
        field_ids=["full_name"],
        purpose="Exercise the real Form Agent state boundary.",
        tags=["accuracy"],
        turns=[
            ScenarioTurn(
                id="start",
                event={"type": "advance"},
                expect=TurnExpectation(
                    effects=["field_selected"],
                    phase="awaiting_answer",
                    field_id="full_name",
                ),
            ),
            ScenarioTurn(
                id="answer",
                event={"type": "message", "content": "ada example"},
                tags=["latest_answer", "contradiction_check", "style_check"],
                expect=TurnExpectation(
                    effects=["proposal"],
                    phase="awaiting_confirmation",
                    field_id="full_name",
                    prepared_value="Ada Example",
                    message_includes_all=["Ada Example", "confirm"],
                    message_excludes_all=["zero"],
                    max_assistant_words=100,
                ),
                behavior=BehaviorExpectation(
                    acknowledges_with_any=["Ada Example"],
                    max_questions=1,
                    speech_suitable=True,
                ),
            ),
            ScenarioTurn(
                id="confirm",
                event={"type": "confirm"},
                visible_user_message="Confirm that.",
                expect=TurnExpectation(
                    effects=["confirmed"],
                    phase="form_complete",
                    field_id="full_name",
                    prepared_value="Ada Example",
                ),
                branches=[
                    TurnBranch(
                        id="proposal-was-clear",
                        when=BranchCondition(
                            previous_message_includes_any=["Ada Example"],
                            previous_expectation_failed=False,
                        ),
                        event={"type": "confirm"},
                        visible_user_message="Branched confirmation.",
                    )
                ],
            ),
        ],
        expected_final=ExpectedFinalState(
            confirmed_values={"full_name": "Ada Example"}
        ),
        allowed_proposals={"full_name": ["Ada Example"]},
    )


def _target() -> ServiceConversationTarget:
    provider = NeverCalledNemotron()
    service = FormAgentService(  # type: ignore[arg-type]
        provider,
        turn_interpretation_enabled=False,
    )
    return ServiceConversationTarget(service, model=provider.model)


def _semantic_target() -> ServiceConversationTarget:
    provider = SemanticNameNemotron()
    service = FormAgentService(provider)  # type: ignore[arg-type]
    return ServiceConversationTarget(service, model=provider.model)


def test_default_suite_covers_required_conversation_behaviours() -> None:
    suite = load_scenario_suite()
    tags = {tag for scenario in suite.scenarios for tag in scenario.tags}

    assert len(suite.personas) == 8
    assert len(suite.scenarios) == 8
    assert {
        "multiple_fields",
        "correction",
        "ambiguity",
        "field_question",
        "interruption",
        "topic_change",
        "skip",
        "frustration",
        "revisit",
    } <= tags
    assert "synthetic" in suite.description.casefold()


def test_voice_reliability_suite_covers_observed_failures() -> None:
    suite = load_scenario_suite(VOICE_RELIABILITY_SCENARIOS)

    assert suite.suite_id == "voice-interview-reliability-v1"
    assert len(suite.personas) == 4
    assert {scenario.id for scenario in suite.scenarios} == {
        "explain-without-invented-date-format",
        "safe-dropdown-near-match",
        "newest-household-count-answer",
        "visible-edited-confirmation",
    }
    assert all(
        "synthetic" in persona.summary.casefold() for persona in suite.personas
    )


def test_human_helper_suite_is_long_form_synthetic_and_multi_fixture() -> None:
    suite = load_scenario_suite(HUMAN_HELPER_SCENARIOS)
    tags = {tag for scenario in suite.scenarios for tag in scenario.tags}
    turn_tags = {
        tag
        for scenario in suite.scenarios
        for turn in scenario.turns
        for tag in turn.tags
    }

    assert suite.schema_version == 2
    assert len(suite.personas) >= 10
    assert len(suite.scenarios) >= 12
    assert sum(len(scenario.turns) for scenario in suite.scenarios) >= 150
    assert len({scenario.fixture for scenario in suite.scenarios}) >= 4
    assert {"human_helper", "long_form"} <= tags
    assert {
        "acknowledgement",
        "side_question_recovery",
        "volunteered_fact_recall",
        "redundant_question_check",
        "unnecessary_push_check",
        "speech_suitability",
        "interruption_recovery",
        "clarification_success",
        "confirmation_boundary",
    } <= turn_tags
    assert any(turn.branches for scenario in suite.scenarios for turn in scenario.turns)
    assert all(
        "synthetic" in persona.summary.casefold() for persona in suite.personas
    )


def test_human_helper_v2_suite_covers_observed_integrated_failures() -> None:
    suite = load_scenario_suite(HUMAN_HELPER_V2_SCENARIOS)
    scenario_tags = {tag for item in suite.scenarios for tag in item.tags}
    visible_messages = {
        turn.visible_user_message or str(turn.event.get("content", ""))
        for item in suite.scenarios
        for turn in item.turns
    }

    assert suite.schema_version == 3
    assert suite.suite_id == "human-helper-experience-v2"
    assert len(suite.scenarios) >= 5
    assert {
        "first_turn_help",
        "progressive_simplification",
        "finite_choice_safety",
        "ambiguous_format",
        "review_understanding",
        "hands_free_continuity",
    } <= scenario_tags
    assert "What does that mean?" in visible_messages
    assert "I live by myself." in visible_messages
    assert "05/19/2011" in visible_messages
    assert "Permit." in visible_messages
    assert "Confirm." in visible_messages
    hands_free = next(
        item for item in suite.scenarios if "hands_free_continuity" in item.tags
    )
    assert len(hands_free.turns) >= 10
    assert all(
        "synthetic" in persona.summary.casefold() for persona in suite.personas
    )


def test_simulator_drives_real_service_and_records_canonical_state() -> None:
    report = asyncio.run(
        ConversationSimulator(_target()).run(_scenario(), _persona())
    )

    assert report.deterministic_failures == []
    assert len(report.transcript) == 3
    assert report.transcript[1].response_effect == {
        "effect": "proposal",
        "field_id": "full_name",
        "original_value": "ada example",
        "prepared_value": "Ada Example",
        "transformation": (
            "Capitalization suggested; spelling and letter order preserved."
        ),
    }
    assert report.actual_form_state == {
        "full_name": {
            "status": "confirmed",
            "confirmed_value": "Ada Example",
        }
    }
    assert report.scores.form_state_accuracy == 1.0
    assert report.scores.invention_failures == 0
    assert report.scores.latest_answer_adherence == 1.0
    assert report.scores.contradiction_failures == 0
    assert report.scores.acknowledgement_rate == 1.0
    assert report.scores.speech_suitability == 1.0
    assert report.scores.human_helper_behavior_rate == 1.0
    assert report.scores.turns_per_confirmed_field == 3.0
    assert report.transcript[2].selected_branch_id == "proposal-was-clear"


def test_read_back_is_a_deterministic_harness_invariant() -> None:
    turn = report_turn = asyncio.run(
        ConversationSimulator(_target()).run(_scenario(), _persona())
    ).transcript[1]
    broken_read_back = report_turn.model_copy(
        update={
            "id": "read-back",
            "index": 3,
            "visible_user_message": "Could you read that back?",
            "request_state": {
                "phase": "awaiting_confirmation",
                "active_field_id": "full_name",
                "pending_proposal": {
                    "field_id": "full_name",
                    "value": "Ada Example",
                },
            },
            "assistant_message": "Full name. What should be entered here?",
        }
    )

    assert _implicit_review_failures([broken_read_back]) == [
        "turn 3 (read-back): assistant did not read back the visibly pending value"
    ]
    assert turn.response_effect is not None


def test_judge_cannot_infer_tenancy_from_living_alone() -> None:
    assert "living alone does not establish sole tenancy" in (
        _JUDGE_SYSTEM_PROMPT.casefold()
    )
    assert "evaluate only this scenario and transcript" in (
        _JUDGE_SYSTEM_PROMPT.casefold()
    )


def test_local_harness_stores_only_privacy_safe_route_diagnostics() -> None:
    report = asyncio.run(
        ConversationSimulator(_semantic_target()).run(_scenario(), _persona())
    )

    diagnostics = report.transcript[1].route_diagnostics
    assert diagnostics == [
        {
            "route": "nemotron_requested",
            "phase": "awaiting_answer",
            "intent": "none",
        },
        {
            "route": "nemotron_interpreted",
            "phase": "awaiting_answer",
            "intent": "answer_current_field",
        },
        {
            "route": "interpreted_action_accepted",
            "phase": "awaiting_answer",
            "intent": "answer_current_field",
        },
    ]
    serialized = json.dumps(diagnostics)
    assert "Ada Example" not in serialized
    assert "full_name" not in serialized


def test_natural_confirmation_counts_only_through_closed_semantic_route() -> None:
    report = asyncio.run(
        ConversationSimulator(_target()).run(_scenario(), _persona())
    )
    explicit_confirmation = report.transcript[2]
    natural_confirmation = explicit_confirmation.model_copy(
        update={
            "user_event": {
                "type": "message",
                "content": "Yes, that's exactly right.",
            },
            "request_state": {
                "phase": "awaiting_confirmation",
                "active_field_id": "full_name",
                "pending_proposal": {
                    "field_id": "full_name",
                    "value": "Ada Example",
                },
            },
            "route_diagnostics": [
                {
                    "route": "interpreted_action_accepted",
                    "phase": "awaiting_confirmation",
                    "intent": "confirm_proposal",
                }
            ],
        }
    )

    assert _confirmation_boundary_failures(natural_confirmation) == 0
    assert _confirmation_boundary_failures(
        natural_confirmation.model_copy(update={"route_diagnostics": []})
    ) == 1


def test_exact_confirmation_counts_through_closed_deterministic_route() -> None:
    report = asyncio.run(
        ConversationSimulator(_target()).run(_scenario(), _persona())
    )
    confirmation = report.transcript[2].model_copy(
        update={
            "user_event": {"type": "message", "content": "Confirm."},
            "request_state": {
                "phase": "awaiting_confirmation",
                "active_field_id": "full_name",
                "pending_proposal": {
                    "field_id": "full_name",
                    "value": "Ada Example",
                },
            },
            "route_diagnostics": [
                {
                    "route": "deterministic_review_command",
                    "phase": "awaiting_confirmation",
                    "intent": "none",
                }
            ],
        }
    )

    assert _confirmation_boundary_failures(confirmation) == 0


def test_suite_report_saves_full_transcript_and_qualitative_scores(
    tmp_path: Path,
) -> None:
    suite = ScenarioSuite(
        suite_id="test-suite",
        description="Synthetic evaluation test suite.",
        personas=[_persona()],
        scenarios=[_scenario()],
    )
    report = asyncio.run(
        run_suite(
            suite,
            _target(),
            label="baseline",
            judge=NemotronQualitativeJudge(StubJudgeService()),
        )
    )

    json_path, markdown_path = save_suite_report(report, tmp_path)
    restored = load_report(json_path)

    assert restored.metrics.form_state_accuracy == 1.0
    assert restored.metrics.judged_naturalness == 4.0
    assert restored.metrics.latest_answer_adherence_rate == 1.0
    assert restored.metrics.contradiction_failure_count == 0
    assert restored.metrics.correctness_gate_passed is True
    assert restored.metrics.human_helper_gate_passed is True
    assert restored.metrics.human_helper_behavior_rate == 1.0
    assert restored.scenarios[0].transcript[0].request_state["phase"] == "asking"
    assert restored.scenarios[0].expected_final_state.confirmed_values == {
        "full_name": "Ada Example"
    }
    assert "**User:** ada example" in markdown_path.read_text(encoding="utf-8")


def test_comparison_reports_metric_deltas_and_failure_changes() -> None:
    suite = ScenarioSuite(
        suite_id="test-suite",
        description="Synthetic evaluation test suite.",
        personas=[_persona()],
        scenarios=[_scenario()],
    )
    baseline = asyncio.run(
        run_suite(
            suite,
            _target(),
            label="baseline",
        )
    )
    baseline_scenario = baseline.scenarios[0].model_copy(
        update={"deterministic_failures": ["test weakness"]}
    )
    baseline = baseline.model_copy(
        update={
            "scenarios": [baseline_scenario],
            "metrics": baseline.metrics.model_copy(
                update={
                    "form_state_accuracy": 0.5,
                    "deterministic_failure_count": 1,
                }
            ),
        }
    )
    candidate = asyncio.run(
        run_suite(
            suite,
            _target(),
            label="candidate",
        )
    )

    comparison = compare_suite_reports(baseline, candidate)

    assert comparison.comparable_suite is True
    assert comparison.metric_deltas["form_state_accuracy"].delta == 0.5
    assert comparison.metric_deltas["form_state_accuracy"].direction == (
        "higher_is_better"
    )
    assert comparison.metric_deltas["latest_answer_adherence_rate"].direction == (
        "higher_is_better"
    )
    assert comparison.metric_deltas["contradiction_failure_count"].direction == (
        "lower_is_better"
    )
    assert comparison.fixed_failures == [
        "deterministic-name: test weakness"
    ]


def test_qualitative_judge_retries_one_invalid_rubric() -> None:
    service = RetryJudgeService()
    scenario_report = asyncio.run(
        ConversationSimulator(_target()).run(_scenario(), _persona())
    )

    assessment = asyncio.run(
        NemotronQualitativeJudge(service).assess(scenario_report)
    )

    assert service.calls == 2
    assert assessment.naturalness == 4


def test_qualitative_judge_retries_unsafe_tenancy_inference() -> None:
    service = UnsafeThenGroundedHousingJudgeService()
    scenario_report = asyncio.run(
        ConversationSimulator(_target()).run(_scenario(), _persona())
    )
    living_alone_turn = scenario_report.transcript[1].model_copy(
        update={"visible_user_message": "I live by myself."}
    )
    scenario_report = scenario_report.model_copy(
        update={
            "transcript": [
                scenario_report.transcript[0],
                living_alone_turn,
                scenario_report.transcript[2],
            ]
        }
    )

    assessment = asyncio.run(
        NemotronQualitativeJudge(service).assess(scenario_report)
    )

    assert service.calls == 2
    assert assessment.failure_reasons == []


def test_pairwise_judge_blinds_labels_and_normalizes_winner() -> None:
    scenario_report = asyncio.run(
        ConversationSimulator(_target()).run(_scenario(), _persona())
    )

    assessment = asyncio.run(
        NemotronPairwiseJudge(StubPairwiseJudgeService()).assess(
            scenario_report,
            scenario_report,
            candidate_first=True,
        )
    )

    assert assessment.preferred == "candidate"
    assert assessment.attentiveness_winner == "candidate"
    assert assessment.safety_concern is False


def test_http_payload_shape_matches_existing_agent_interface() -> None:
    request = FormAgentRequest.model_validate(
        {
            "fields": [
                {
                    "id": "name",
                    "label": "Name",
                    "question": "What is your name?",
                    "type": "text",
                }
            ],
            "conversation_state": {
                "phase": "asking",
                "active_field_id": None,
                "pending_proposal": None,
            },
            "event": {"type": "advance"},
        }
    )

    payload = request.model_dump(mode="json")

    assert set(payload) == {
        "form_context",
        "fields",
        "conversation_state",
        "event",
        "assistance_preferences",
        "history",
    }
    assert payload["event"] == {"type": "advance"}


def test_http_target_posts_to_existing_agent_endpoint() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "assistant_message": "Name. What should be entered here?",
                "effect": {"effect": "field_selected", "field_id": "name"},
                "conversation_state": {
                    "phase": "awaiting_answer",
                    "active_field_id": "name",
                    "pending_proposal": None,
                },
                "guidance": [],
                "web_guidance": None,
            },
        )

    request = FormAgentRequest.model_validate(
        {
            "fields": [{"id": "name", "label": "Name", "type": "text"}],
            "conversation_state": {
                "phase": "asking",
                "active_field_id": None,
                "pending_proposal": None,
            },
            "event": {"type": "advance"},
        }
    )
    target = HttpConversationTarget(
        "http://example.test",
        transport=httpx.MockTransport(handler),
    )

    response = asyncio.run(target.respond(request))

    assert captured["path"] == "/agent/respond"
    assert captured["payload"]["event"] == {"type": "advance"}
    assert response.effect.effect == "field_selected"
