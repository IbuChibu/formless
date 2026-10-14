from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from app.services.form_agent import FormAgentRequest, FormAgentService
from evaluations.conversation_harness.judge import NemotronQualitativeJudge
from evaluations.conversation_harness.models import (
    ConversationScenario,
    ExpectedFinalState,
    Persona,
    ScenarioSuite,
    ScenarioTurn,
    TurnExpectation,
)
from evaluations.conversation_harness.reporting import (
    compare_suite_reports,
    load_report,
    save_suite_report,
)
from evaluations.conversation_harness.runner import run_suite
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


class NeverCalledNemotron:
    model = "test-never-called"

    async def complete(self, **kwargs: Any) -> str:
        raise AssertionError("This deterministic scenario should not call Nemotron")


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
            ),
        ],
        expected_final=ExpectedFinalState(
            confirmed_values={"full_name": "Ada Example"}
        ),
        allowed_proposals={"full_name": ["Ada Example"]},
    )


def _target() -> ServiceConversationTarget:
    provider = NeverCalledNemotron()
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
