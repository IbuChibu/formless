from __future__ import annotations

import asyncio
from typing import Any

from evaluations.form_agent_conversation_quality import (
    conversation_quality_scenarios,
    run_conversation_quality_evaluation,
)


class ScriptedNemotronService:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
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
            '{"action":"explain","message":"Choose whether you rent, '
            'own, or stay somewhere else. You can tell me which applies, '
            'ask another question, or skip it.",'
            '"field_id":"active_field"}',
        ]
    )

    report = asyncio.run(
        run_conversation_quality_evaluation(service)  # type: ignore[arg-type]
    )

    assert report.failures == ()
    assert report.metrics.total_scenarios == 3
    assert report.metrics.valid_response_rate == 1.0
    assert report.metrics.directness_rate == 1.0
    assert report.metrics.contextual_relevance_rate == 1.0
    assert report.metrics.useful_next_step_rate == 1.0
    assert report.metrics.average_latency_ms >= 0
    assert report.metrics.total_model_calls == 3
    assert report.metrics.model_calls_per_scenario == 1.0
    assert len(service.calls) == 3


def test_conversation_quality_scenarios_are_small_and_fixed() -> None:
    scenarios = conversation_quality_scenarios()

    assert len(scenarios) == 3
    assert {scenario.name for scenario in scenarios} == {
        "usual-address-date",
        "monthly-income",
        "pronoun-follow-up",
    }
    assert all(scenario.context_terms for scenario in scenarios)
    assert all(scenario.next_step_terms for scenario in scenarios)
