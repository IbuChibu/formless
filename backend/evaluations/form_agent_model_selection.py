"""Compare two Nemotron models on the fixed Form Agent live evaluation.

Run explicitly with configured Nebius credentials and a candidate model:

    NEBIUS_CANDIDATE_MODEL=<model-id> \
        python -m evaluations.form_agent_model_selection

The models run sequentially with the same scenarios and Form Agent code. The
normal test suite uses deterministic doubles and never makes a network request.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Mapping, Optional

from app.services.nemotron_service import (
    NemotronConfigurationError,
    NemotronService,
    NemotronSettings,
)
from evaluations.form_agent_conversation_quality import (
    ConversationQualityReport,
    run_conversation_quality_evaluation,
)


POSITIVE_QUALITY_METRICS = (
    "valid_response_rate",
    "directness_rate",
    "contextual_relevance_rate",
    "useful_next_step_rate",
    "material_rephrasing_rate",
    "progressive_simplification_rate",
    "conversation_repair_success_rate",
)
LOWER_IS_BETTER_METRICS = ("repeated_response_rate",)


@dataclass(frozen=True)
class ModelSelectionThresholds:
    material_quality_improvement: float = 0.05
    quality_regression_tolerance: float = 0.0
    maximum_latency_ratio: float = 4.0
    maximum_average_latency_ms: float = 2500.0


@dataclass(frozen=True)
class ModelSelectionComparison:
    primary: ConversationQualityReport
    candidate: ConversationQualityReport
    metric_deltas: Mapping[str, float]
    latency_ratio: Optional[float]
    recommendation: str
    reasons: tuple[str, ...]
    thresholds: ModelSelectionThresholds

    def as_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary.as_dict(),
            "candidate": self.candidate.as_dict(),
            "metric_deltas": dict(self.metric_deltas),
            "latency_ratio": self.latency_ratio,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "thresholds": asdict(self.thresholds),
        }


async def run_model_selection_comparison(
    primary_service: NemotronService,
    candidate_service: NemotronService,
    *,
    thresholds: Optional[ModelSelectionThresholds] = None,
) -> ModelSelectionComparison:
    """Run the fixed evaluation sequentially and compare the reports."""

    primary_report = await run_conversation_quality_evaluation(primary_service)
    candidate_report = await run_conversation_quality_evaluation(candidate_service)
    return compare_model_reports(
        primary_report,
        candidate_report,
        thresholds=thresholds,
    )


def compare_model_reports(
    primary: ConversationQualityReport,
    candidate: ConversationQualityReport,
    *,
    thresholds: Optional[ModelSelectionThresholds] = None,
) -> ModelSelectionComparison:
    selected_thresholds = thresholds or ModelSelectionThresholds()
    metric_deltas = _metric_deltas(primary, candidate)
    latency_ratio = _latency_ratio(primary, candidate)
    disqualifying_reasons: list[str] = []

    if candidate.metrics.safety_boundary_failures:
        disqualifying_reasons.append(
            "candidate produced one or more safety-boundary failures"
        )

    for metric_name in POSITIVE_QUALITY_METRICS:
        delta = metric_deltas[metric_name]
        if delta < -selected_thresholds.quality_regression_tolerance:
            disqualifying_reasons.append(
                f"candidate regressed {metric_name} by {abs(delta):.3f}"
            )

    for metric_name in LOWER_IS_BETTER_METRICS:
        delta = metric_deltas[metric_name]
        if delta > selected_thresholds.quality_regression_tolerance:
            disqualifying_reasons.append(
                f"candidate regressed {metric_name} by {delta:.3f}"
            )

    if (
        candidate.metrics.average_latency_ms
        > selected_thresholds.maximum_average_latency_ms
    ):
        disqualifying_reasons.append(
            "candidate exceeded the average latency budget "
            f"({candidate.metrics.average_latency_ms:.3f} ms)"
        )
    if (
        latency_ratio is not None
        and latency_ratio > selected_thresholds.maximum_latency_ratio
    ):
        disqualifying_reasons.append(
            "candidate exceeded the relative latency budget "
            f"({latency_ratio:.3f}x primary)"
        )

    if disqualifying_reasons:
        return ModelSelectionComparison(
            primary=primary,
            candidate=candidate,
            metric_deltas=metric_deltas,
            latency_ratio=latency_ratio,
            recommendation="keep_primary",
            reasons=tuple(disqualifying_reasons),
            thresholds=selected_thresholds,
        )

    improvements = [
        metric_name
        for metric_name in POSITIVE_QUALITY_METRICS
        if metric_deltas[metric_name]
        >= selected_thresholds.material_quality_improvement
    ]
    improvements.extend(
        metric_name
        for metric_name in LOWER_IS_BETTER_METRICS
        if metric_deltas[metric_name]
        <= -selected_thresholds.material_quality_improvement
    )

    if improvements:
        reasons = (
            "candidate materially improved: " + ", ".join(improvements),
            "candidate stayed within the safety and latency budgets",
        )
        recommendation = "select_candidate"
    else:
        reasons = (
            "automated metrics found no material quality difference",
            "review the side-by-side scenario messages before keeping the primary",
        )
        recommendation = "manual_review"

    return ModelSelectionComparison(
        primary=primary,
        candidate=candidate,
        metric_deltas=metric_deltas,
        latency_ratio=latency_ratio,
        recommendation=recommendation,
        reasons=reasons,
        thresholds=selected_thresholds,
    )


def services_from_environment(
    *,
    candidate_model: Optional[str] = None,
    environment: Optional[Mapping[str, str]] = None,
) -> tuple[NemotronService, NemotronService]:
    values = os.environ if environment is None else environment
    primary_settings = NemotronSettings.from_environment(values)
    selected_candidate = (
        candidate_model
        or values.get("NEBIUS_CANDIDATE_MODEL", "")
    ).strip()
    if not selected_candidate:
        raise NemotronConfigurationError(
            "Set NEBIUS_CANDIDATE_MODEL to a stronger Token Factory model ID"
        )
    if selected_candidate == primary_settings.model:
        raise NemotronConfigurationError(
            "The candidate model must differ from NEBIUS_MODEL"
        )

    candidate_settings = NemotronSettings(
        api_key=primary_settings.api_key,
        base_url=primary_settings.base_url,
        model=selected_candidate,
    )
    return (
        NemotronService(primary_settings),
        NemotronService(candidate_settings),
    )


def _metric_deltas(
    primary: ConversationQualityReport,
    candidate: ConversationQualityReport,
) -> dict[str, float]:
    return {
        metric_name: round(
            getattr(candidate.metrics, metric_name)
            - getattr(primary.metrics, metric_name),
            3,
        )
        for metric_name in (*POSITIVE_QUALITY_METRICS, *LOWER_IS_BETTER_METRICS)
    }


def _latency_ratio(
    primary: ConversationQualityReport,
    candidate: ConversationQualityReport,
) -> Optional[float]:
    primary_latency = primary.metrics.average_latency_ms
    candidate_latency = candidate.metrics.average_latency_ms
    if primary_latency <= 0:
        return 1.0 if candidate_latency <= 0 else None
    return round(candidate_latency / primary_latency, 3)


async def _run_live(candidate_model: Optional[str]) -> None:
    try:
        primary_service, candidate_service = services_from_environment(
            candidate_model=candidate_model,
        )
    except NemotronConfigurationError as error:
        raise SystemExit(str(error)) from error

    comparison = await run_model_selection_comparison(
        primary_service,
        candidate_service,
    )
    print(json.dumps(comparison.as_dict(), indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare NEBIUS_MODEL with one stronger Nemotron candidate using "
            "the fixed Form Agent conversation-quality evaluation."
        )
    )
    parser.add_argument(
        "--candidate-model",
        help=(
            "Token Factory model ID. Defaults to NEBIUS_CANDIDATE_MODEL."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    asyncio.run(_run_live(arguments.candidate_model))
