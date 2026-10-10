"""Optional live evaluation for conversational Form Agent responses.

Run explicitly with configured Nebius credentials:

    python -m evaluations.form_agent_conversation_quality

The normal test suite exercises this evaluator with a deterministic service and
never makes a network request.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json
from time import perf_counter
from typing import Any, Optional, Protocol

from app.services.form_agent import FormAgentRequest, FormAgentService
from app.services.nemotron_service import (
    NemotronConfigurationError,
    NemotronService,
    NemotronServiceError,
)


@dataclass(frozen=True)
class ConversationQualityScenario:
    name: str
    question: str
    user_message: str
    context_terms: tuple[str, ...]
    next_step_terms: tuple[str, ...] = (
        "answer",
        "tell me",
        "ask",
        "skip",
    )
    phase: str = "awaiting_answer"
    history: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ConversationQualityMetrics:
    total_scenarios: int
    valid_response_rate: float
    directness_rate: float
    contextual_relevance_rate: float
    useful_next_step_rate: float
    average_latency_ms: float
    total_model_calls: int
    model_calls_per_scenario: float


@dataclass(frozen=True)
class ConversationQualityReport:
    metrics: ConversationQualityMetrics
    failures: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "metrics": asdict(self.metrics),
            "failures": list(self.failures),
        }


class _NemotronCompletionService(Protocol):
    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 600,
        json_response: bool = False,
    ) -> str: ...


class _MeasuredNemotronService:
    def __init__(self, service: _NemotronCompletionService) -> None:
        self._service = service
        self.call_count = 0
        self.latencies_ms: list[float] = []

    async def complete(self, **kwargs: Any) -> str:
        self.call_count += 1
        started_at = perf_counter()
        try:
            return await self._service.complete(**kwargs)
        finally:
            self.latencies_ms.append((perf_counter() - started_at) * 1000)


def conversation_quality_scenarios() -> tuple[ConversationQualityScenario, ...]:
    return (
        ConversationQualityScenario(
            name="usual-address-date",
            question=(
                "The date you began living at the address you ordinarily "
                "reside at"
            ),
            user_message="What does this mean?",
            context_terms=(
                "usual",
                "main",
                "normally",
                "ordinarily",
                "living",
            ),
        ),
        ConversationQualityScenario(
            name="monthly-income",
            question="What is your gross monthly household income?",
            user_message="Can you explain that in plain language?",
            context_terms=("income", "money", "earn", "monthly", "month"),
        ),
        ConversationQualityScenario(
            name="pronoun-follow-up",
            question="Which option best describes where you live?",
            user_message="Explain that more simply.",
            context_terms=("rent", "own", "stay", "live", "housing"),
            phase="awaiting_clarification",
            history=(
                ("user", "What is this asking?"),
                (
                    "assistant",
                    "It asks which living arrangement applies to you.",
                ),
            ),
        ),
    )


async def run_conversation_quality_evaluation(
    service: _NemotronCompletionService,
    *,
    scenarios: Optional[tuple[ConversationQualityScenario, ...]] = None,
) -> ConversationQualityReport:
    selected = scenarios or conversation_quality_scenarios()
    failures: list[str] = []
    valid_responses = 0
    direct_responses = 0
    contextually_relevant_responses = 0
    useful_next_steps = 0
    total_calls = 0
    latencies_ms: list[float] = []

    for scenario in selected:
        measured_service = _MeasuredNemotronService(service)
        request = _scenario_request(scenario)
        try:
            response = await FormAgentService(  # type: ignore[arg-type]
                measured_service
            ).respond(request)
        except (NemotronServiceError, RuntimeError) as error:
            failures.append(f"{scenario.name}: {error}")
            total_calls += measured_service.call_count
            latencies_ms.extend(measured_service.latencies_ms)
            continue

        total_calls += measured_service.call_count
        latencies_ms.extend(measured_service.latencies_ms)
        if response.action.action != "explain":
            failures.append(
                f'{scenario.name}: expected "explain", got '
                f'"{response.action.action}"'
            )
            continue

        valid_responses += 1
        message = response.action.message.strip()
        normalized = " ".join(message.casefold().split())
        if _is_direct(message):
            direct_responses += 1
        else:
            failures.append(f"{scenario.name}: response was not direct")
        if any(term in normalized for term in scenario.context_terms):
            contextually_relevant_responses += 1
        else:
            failures.append(
                f"{scenario.name}: response did not reference the field context"
            )
        if any(term in normalized for term in scenario.next_step_terms):
            useful_next_steps += 1
        else:
            failures.append(
                f"{scenario.name}: response did not offer a useful next step"
            )

    scenario_count = len(selected)
    return ConversationQualityReport(
        metrics=ConversationQualityMetrics(
            total_scenarios=scenario_count,
            valid_response_rate=_rate(valid_responses, scenario_count),
            directness_rate=_rate(direct_responses, scenario_count),
            contextual_relevance_rate=_rate(
                contextually_relevant_responses,
                scenario_count,
            ),
            useful_next_step_rate=_rate(useful_next_steps, scenario_count),
            average_latency_ms=round(_average(latencies_ms), 3),
            total_model_calls=total_calls,
            model_calls_per_scenario=(
                round(total_calls / scenario_count, 3) if scenario_count else 0.0
            ),
        ),
        failures=tuple(failures),
    )


def _scenario_request(
    scenario: ConversationQualityScenario,
) -> FormAgentRequest:
    return FormAgentRequest.model_validate(
        {
            "form_context": {
                "title": "Conversation quality evaluation form",
                "instructions": [],
            },
            "fields": [
                {
                    "id": "active_field",
                    "label": scenario.question,
                    "question": scenario.question,
                    "type": "text",
                    "status": "unanswered",
                }
            ],
            "conversation_state": {
                "phase": scenario.phase,
                "active_field_id": "active_field",
                "pending_proposal": None,
            },
            "event": {"type": "message", "content": scenario.user_message},
            "history": [
                {"role": role, "content": content}
                for role, content in scenario.history
            ],
        }
    )


def _is_direct(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    indirect_openings = (
        "as an ai",
        "i cannot help",
        "i can't help",
        "verified guidance is unavailable",
        "live web guidance is unavailable",
    )
    return (
        0 < len(message.split()) <= 100
        and not normalized.startswith(indirect_openings)
    )


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


async def _run_live() -> None:
    try:
        service = NemotronService.from_environment()
        report = await run_conversation_quality_evaluation(service)
    except NemotronConfigurationError as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(report.as_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(_run_live())
