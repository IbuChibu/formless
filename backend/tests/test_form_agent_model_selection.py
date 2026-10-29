from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.services.nemotron_service import NemotronConfigurationError
from evaluations.form_agent_conversation_quality import (
    ConversationQualityMetrics,
    ConversationQualityReport,
)
from evaluations.form_agent_model_selection import (
    compare_model_reports,
    run_model_selection_comparison,
    services_from_environment,
)


def _report(
    model: str,
    *,
    valid: float = 1.0,
    direct: float = 1.0,
    context: float = 1.0,
    next_step: float = 1.0,
    repeated: float = 0.0,
    rephrasing: float = 1.0,
    simplification: float = 1.0,
    repair: float = 1.0,
    safety_failures: int = 0,
    latency_ms: float = 400.0,
) -> ConversationQualityReport:
    return ConversationQualityReport(
        model=model,
        metrics=ConversationQualityMetrics(
            total_scenarios=9,
            valid_response_rate=valid,
            directness_rate=direct,
            contextual_relevance_rate=context,
            useful_next_step_rate=next_step,
            repeated_response_rate=repeated,
            material_rephrasing_rate=rephrasing,
            progressive_simplification_rate=simplification,
            conversation_repair_success_rate=repair,
            safety_boundary_failures=safety_failures,
            average_latency_ms=latency_ms,
            total_model_calls=6,
            model_calls_per_scenario=0.667,
        ),
        failures=(),
        samples=(),
    )


def test_candidate_is_selected_for_material_quality_improvement() -> None:
    primary = _report(
        "nvidia/lightning",
        context=0.778,
        next_step=0.889,
        repair=0.667,
    )
    candidate = _report(
        "nvidia/stronger",
        latency_ms=900.0,
    )

    comparison = compare_model_reports(primary, candidate)

    assert comparison.recommendation == "select_candidate"
    assert comparison.metric_deltas["contextual_relevance_rate"] == 0.222
    assert comparison.metric_deltas["conversation_repair_success_rate"] == 0.333
    assert comparison.latency_ratio == 2.25


def test_candidate_is_rejected_for_safety_or_quality_regression() -> None:
    primary = _report("nvidia/lightning")
    candidate = _report(
        "nvidia/stronger",
        context=0.889,
        safety_failures=1,
    )

    comparison = compare_model_reports(primary, candidate)

    assert comparison.recommendation == "keep_primary"
    assert any("safety-boundary" in reason for reason in comparison.reasons)
    assert any("contextual_relevance_rate" in reason for reason in comparison.reasons)


def test_tied_metrics_require_side_by_side_manual_review() -> None:
    primary = _report("nvidia/lightning")
    candidate = _report("nvidia/stronger", latency_ms=800.0)

    comparison = compare_model_reports(primary, candidate)

    assert comparison.recommendation == "manual_review"
    assert comparison.metric_deltas["valid_response_rate"] == 0.0
    assert comparison.latency_ratio == 2.0


def test_candidate_is_rejected_when_latency_budget_is_exceeded() -> None:
    primary = _report(
        "nvidia/lightning",
        context=0.889,
        latency_ms=400.0,
    )
    candidate = _report(
        "nvidia/stronger",
        latency_ms=2000.0,
    )

    comparison = compare_model_reports(primary, candidate)

    assert comparison.recommendation == "keep_primary"
    assert comparison.latency_ratio == 5.0
    assert any("relative latency" in reason for reason in comparison.reasons)


def test_services_from_environment_uses_one_key_and_two_model_ids() -> None:
    primary, candidate = services_from_environment(
        environment={
            "NEBIUS_API_KEY": "test-secret",
            "NEBIUS_BASE_URL": "https://token-factory.test/v1",
            "NEBIUS_MODEL": "nvidia/lightning",
            "NEBIUS_CANDIDATE_MODEL": "nvidia/stronger",
        }
    )

    assert primary.model == "nvidia/lightning"
    assert candidate.model == "nvidia/stronger"


def test_services_from_environment_requires_a_distinct_candidate() -> None:
    environment = {
        "NEBIUS_API_KEY": "test-secret",
        "NEBIUS_MODEL": "nvidia/lightning",
    }

    with pytest.raises(NemotronConfigurationError, match="CANDIDATE_MODEL"):
        services_from_environment(environment=environment)

    with pytest.raises(NemotronConfigurationError, match="must differ"):
        services_from_environment(
            environment={
                **environment,
                "NEBIUS_CANDIDATE_MODEL": "nvidia/lightning",
            }
        )


class _OrderedScriptedService:
    def __init__(
        self,
        model: str,
        order: list[str],
    ) -> None:
        self.model = model
        self._order = order
        self._responses = [
            '{"action":"explain","message":"This asks when you started '
            'living at your usual home. You can answer or skip.",'
            '"field_id":"active_field"}',
            '{"action":"explain","message":"This asks for the money your '
            'household earns each month before deductions. You can answer or '
            'skip.","field_id":"active_field"}',
            '{"action":"explain","message":"When did you move into your '
            'current home? You can answer or ask about a word.",'
            '"field_id":"active_field"}',
            '{"action":"explain","message":"Choose whether you rent, own, '
            'or stay with someone. Tell me which applies.",'
            '"field_id":"active_field"}',
            '{"action":"explain","message":"For example, a move-in date is '
            'when someone began living in their current home. Which part is '
            'unclear?","field_id":"active_field"}',
            '{"action":"conversation","message":"Of course. We can pause '
            'and resume when you are ready.","field_id":"active_field"}',
        ]

    async def complete(self, **kwargs: Any) -> str:
        self._order.append(self.model)
        if "conversational turn interpreter" in kwargs["system_prompt"]:
            prompt = kwargs["user_prompt"]
            if "my email is jane@example.com" in prompt:
                return json.dumps(
                    {
                        "intent": "answer_current_field",
                        "confidence": "high",
                        "needs_clarification": False,
                        "clarification_reason": None,
                        "candidates": [
                            {
                                "field_id": "active_field",
                                "value": "jane@example.com",
                                "evidence": "jane@example.com",
                            }
                        ],
                        "referenced_field_id": None,
                        "assistance_needs": [],
                        "interaction_mode": None,
                        "assistant_reply": (
                            "I understood jane@example.com. Please review "
                            "and confirm it."
                        ),
                    }
                )
            unrelated = "Can we pause for a minute?" in prompt
            return json.dumps(
                {
                    "intent": "unrelated" if unrelated else "ask_explanation",
                    "confidence": "high",
                    "needs_clarification": False,
                    "clarification_reason": None,
                    "candidates": [],
                    "referenced_field_id": None,
                    "assistance_needs": [],
                    "interaction_mode": None,
                    "assistant_reply": (
                        "Of course. We can pause and resume when you are ready."
                        if unrelated
                        else "I'll explain that in simpler words."
                    ),
                }
            )
        return self._responses.pop(0)


def test_live_comparison_runs_primary_then_candidate_sequentially() -> None:
    order: list[str] = []
    primary = _OrderedScriptedService("primary", order)
    candidate = _OrderedScriptedService("candidate", order)

    comparison = asyncio.run(
        run_model_selection_comparison(  # type: ignore[arg-type]
            primary,
            candidate,
        )
    )

    assert order == ["primary"] * 12 + ["candidate"] * 12
    assert comparison.primary.model == "primary"
    assert comparison.candidate.model == "candidate"
    assert comparison.recommendation == "manual_review"
    assert len(comparison.primary.samples) == 9
    assert len(comparison.candidate.samples) == 9
