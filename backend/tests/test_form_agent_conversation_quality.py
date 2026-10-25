from __future__ import annotations

import asyncio
from typing import Any

from evaluations.form_agent_conversation_quality import (
    conversation_quality_scenarios,
    run_conversation_quality_evaluation,
)


class ScriptedNemotronService:
    model = "nvidia/test-nemotron"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if "bounded turn interpreter" in kwargs["system_prompt"]:
            intent = (
                "unrelated"
                if "Can we pause for a minute?" in kwargs["user_prompt"]
                else "ask_explanation"
            )
            return (
                '{"intent":"' + intent + '","confidence":"high",'
                '"needs_clarification":false,"clarification_reason":null,'
                '"candidates":[],"referenced_field_id":null,'
                '"assistance_needs":[],"interaction_mode":null}'
            )
        return self.responses.pop(0)


def test_conversation_quality_evaluation_reports_required_metrics() -> None:
    service = ScriptedNemotronService(
        [
            '{"action":"explain","message":"This asks when you started '
            'living at your usual home. You can tell me the date, ask '
            'another question, or skip it for now.",'
            '"field_id":"active_field"}',
            '{"action":"explain","message":"This asks for the money your '
            'household earns in a typical month before deductions. You can '
            'answer now, ask for more help, or skip it.",'
            '"field_id":"active_field"}',
            '{"action":"explain","message":"When did you move into the '
            'home you live in now? You can tell me the date or ask about a '
            'specific word.","field_id":"active_field"}',
            '{"action":"explain","message":"Choose whether you rent, '
            'own, or stay somewhere else. You can tell me which applies, '
            'ask another question, or skip it.",'
            '"field_id":"active_field"}',
            '{"action":"explain","message":"For example, someone who '
            'moved into their current home on 5 March 2021 would call that '
            'their move-in date, not yours. Which word or part is unclear?",'
            '"field_id":"active_field"}',
            '{"action":"conversation","message":"Of course. We can '
            'pause here and continue whenever you are ready.",'
            '"field_id":"active_field"}',
        ]
    )

    report = asyncio.run(
        run_conversation_quality_evaluation(service)  # type: ignore[arg-type]
    )

    assert report.failures == ()
    assert report.model == "nvidia/test-nemotron"
    assert report.metrics.total_scenarios == 9
    assert report.metrics.valid_response_rate == 1.0
    assert report.metrics.directness_rate == 1.0
    assert report.metrics.contextual_relevance_rate == 1.0
    assert report.metrics.useful_next_step_rate == 1.0
    assert report.metrics.repeated_response_rate == 0.0
    assert report.metrics.material_rephrasing_rate == 1.0
    assert report.metrics.progressive_simplification_rate == 1.0
    assert report.metrics.conversation_repair_success_rate == 1.0
    assert report.metrics.safety_boundary_failures == 0
    assert report.metrics.average_latency_ms >= 0
    assert report.metrics.total_model_calls == 12
    assert report.metrics.model_calls_per_scenario == 1.333
    assert len(report.samples) == 9
    assert report.samples[0].scenario == "usual-address-date"
    assert report.samples[0].assistant_message is not None
    assert report.samples[0].model_calls == 2
    assert report.samples[-1].scenario == "post-completion-summary"
    assert report.samples[-1].model_calls == 0
    assert len(service.calls) == 12


def test_conversation_quality_scenarios_are_small_and_fixed() -> None:
    scenarios = conversation_quality_scenarios()

    assert len(scenarios) == 9
    assert {scenario.name for scenario in scenarios} == {
        "usual-address-date",
        "monthly-income",
        "move-in-date-simplification",
        "housing-pronoun-follow-up",
        "continued-confusion",
        "natural-pause-question",
        "email-framing",
        "natural-chat-start",
        "post-completion-summary",
    }
    assert all(scenario.context_terms for scenario in scenarios)
    assert all(scenario.next_step_terms for scenario in scenarios)
    assert {
        scenario.expected_objective for scenario in scenarios
    } == {
        "initial_paraphrase",
        "simplify_previous_explanation",
        "clarify_what_is_confusing",
        "natural_conversation",
        None,
    }
