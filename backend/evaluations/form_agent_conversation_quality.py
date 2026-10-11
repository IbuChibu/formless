"""Optional live evaluation for conversational Form Agent responses.

Run explicitly with configured Nebius credentials:

    python -m evaluations.form_agent_conversation_quality

The normal test suite exercises this evaluator with a deterministic service and
never makes a network request.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
import re
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
    expected_objective: Optional[str]
    expected_action: str = "explain"
    accepted_actions: tuple[str, ...] = ()
    expected_model_calls: int = 1
    maximum_model_calls: Optional[int] = None
    field_type: str = "text"
    field_options: tuple[str, ...] = ()
    field_status: str = "unanswered"
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
    repeated_response_rate: float
    material_rephrasing_rate: float
    progressive_simplification_rate: float
    conversation_repair_success_rate: float
    safety_boundary_failures: int
    average_latency_ms: float
    total_model_calls: int
    model_calls_per_scenario: float


@dataclass(frozen=True)
class ConversationQualitySample:
    scenario: str
    action: Optional[str]
    assistant_message: Optional[str]
    model_calls: int
    model_latency_ms: float
    error: Optional[str] = None


@dataclass(frozen=True)
class ConversationQualityReport:
    model: str
    metrics: ConversationQualityMetrics
    failures: tuple[str, ...]
    samples: tuple[ConversationQualitySample, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "metrics": asdict(self.metrics),
            "failures": list(self.failures),
            "samples": [asdict(sample) for sample in self.samples],
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
        self.calls: list[dict[str, Any]] = []
        self.latencies_ms: list[float] = []

    async def complete(self, **kwargs: Any) -> str:
        self.call_count += 1
        self.calls.append(kwargs)
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
            expected_objective="initial_paraphrase",
            accepted_actions=("explain", "conversation"),
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
            expected_objective="initial_paraphrase",
            accepted_actions=("explain", "conversation"),
            context_terms=("income", "money", "earn", "monthly", "month"),
        ),
        ConversationQualityScenario(
            name="move-in-date-simplification",
            question=(
                "The date you began living at the address you ordinarily "
                "reside at"
            ),
            user_message="Explain that more simply.",
            expected_objective="simplify_previous_explanation",
            accepted_actions=("explain", "conversation"),
            context_terms=("home", "move", "moved", "living"),
            phase="awaiting_clarification",
            history=(
                ("user", "What does this mean?"),
                (
                    "assistant",
                    "It asks for the date you began living at the address "
                    "where you are ordinarily resident.",
                ),
            ),
        ),
        ConversationQualityScenario(
            name="housing-pronoun-follow-up",
            question="Which option best describes where you live?",
            user_message="Explain that more simply.",
            expected_objective="simplify_previous_explanation",
            accepted_actions=("explain", "conversation"),
            context_terms=("rent", "own", "stay", "live", "housing"),
            phase="awaiting_clarification",
            field_type="dropdown",
            field_options=("Rent", "Own", "Staying with someone"),
            history=(
                ("user", "What is this asking?"),
                (
                    "assistant",
                    "It asks which living arrangement applies to you.",
                ),
            ),
        ),
        ConversationQualityScenario(
            name="continued-confusion",
            question=(
                "The date you began living at the address you ordinarily "
                "reside at"
            ),
            user_message="I still don't understand.",
            expected_objective="clarify_what_is_confusing",
            accepted_actions=("explain", "conversation"),
            context_terms=("home", "move", "moved", "living"),
            next_step_terms=(
                "which",
                "what",
                "part",
                "word",
                "phrase",
                "tell me",
                "let me know",
                "example",
            ),
            phase="awaiting_clarification",
            history=(
                ("user", "What does this mean?"),
                (
                    "assistant",
                    "It asks for the date you began living at the address "
                    "where you are ordinarily resident.",
                ),
                ("user", "Explain that more simply."),
                (
                    "assistant",
                    "When did your current address become your usual "
                    "residence?",
                ),
            ),
        ),
        ConversationQualityScenario(
            name="natural-pause-question",
            question=(
                "The date you began living at the address you ordinarily "
                "reside at"
            ),
            user_message="Can we pause for a minute?",
            expected_objective="natural_conversation",
            expected_action="conversation",
            accepted_actions=("conversation",),
            context_terms=("pause", "wait", "ready", "resume"),
            next_step_terms=("ready", "resume", "continue", "pause"),
        ),
        ConversationQualityScenario(
            name="email-framing",
            question="Employee email address",
            user_message="my email is jane@example.com",
            expected_objective=None,
            expected_action="propose",
            expected_model_calls=0,
            context_terms=("email", "jane@example.com"),
            next_step_terms=("review", "confirmation", "confirm"),
        ),
        ConversationQualityScenario(
            name="natural-chat-start",
            question="What is your full name?",
            user_message="Hi, can you help me with this form?",
            expected_objective=None,
            expected_action="next",
            expected_model_calls=0,
            context_terms=("full name", "name"),
            next_step_terms=("start", "name", "question"),
            phase="asking",
        ),
        ConversationQualityScenario(
            name="post-completion-summary",
            question="Full name",
            user_message="What did we complete?",
            expected_objective=None,
            expected_action="next",
            expected_model_calls=0,
            field_status="confirmed",
            context_terms=("reviewed", "confirmed", "complete"),
            next_step_terms=("review", "pdf", "download"),
            phase="form_complete",
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
    repeated_responses = 0
    material_rephrasings = 0
    progressive_simplifications = 0
    successful_repairs = 0
    safety_boundary_failures = 0
    repair_scenario_count = 0
    total_calls = 0
    latencies_ms: list[float] = []
    samples: list[ConversationQualitySample] = []

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
            samples.append(
                ConversationQualitySample(
                    scenario=scenario.name,
                    action=None,
                    assistant_message=None,
                    model_calls=measured_service.call_count,
                    model_latency_ms=round(
                        sum(measured_service.latencies_ms),
                        3,
                    ),
                    error=str(error),
                )
            )
            continue

        total_calls += measured_service.call_count
        latencies_ms.extend(measured_service.latencies_ms)
        actual_objective = _turn_objective_from_calls(measured_service.calls)
        if (
            scenario.expected_objective is not None
            and actual_objective != scenario.expected_objective
        ):
            failures.append(
                f"{scenario.name}: expected objective "
                f'"{scenario.expected_objective}", got '
                f'"{actual_objective}"'
            )
        maximum_model_calls = (
            scenario.maximum_model_calls
            if scenario.maximum_model_calls is not None
            else scenario.expected_model_calls + int(scenario.expected_model_calls > 0)
        )
        if not (
            scenario.expected_model_calls
            <= measured_service.call_count
            <= maximum_model_calls
        ):
            failures.append(
                f"{scenario.name}: expected between "
                f"{scenario.expected_model_calls} and {maximum_model_calls} "
                f"model call(s), got {measured_service.call_count}"
            )
        accepted_actions = scenario.accepted_actions or (
            scenario.expected_action,
        )
        samples.append(
            ConversationQualitySample(
                scenario=scenario.name,
                action=response.action.action,
                assistant_message=response.action.message.strip(),
                model_calls=measured_service.call_count,
                model_latency_ms=round(
                    sum(measured_service.latencies_ms),
                    3,
                ),
            )
        )
        if response.action.action not in accepted_actions:
            failures.append(
                f"{scenario.name}: expected one of {accepted_actions}, got "
                f'"{response.action.action}"'
            )
            continue

        boundary_failure = _safety_boundary_failure(scenario, request, response)
        if boundary_failure is not None:
            safety_boundary_failures += 1
            failures.append(f"{scenario.name}: {boundary_failure}")

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
            has_useful_next_step = True
        else:
            has_useful_next_step = False
            failures.append(
                f"{scenario.name}: response did not offer a useful next step"
            )

        previous_explanation = _last_assistant_message(scenario.history)
        if previous_explanation is not None:
            repair_scenario_count += 1
            is_repeated = _explanations_are_near_duplicate(
                previous_explanation,
                message,
            )
            is_material_rephrasing = not is_repeated
            is_progressively_simpler = _is_progressively_simpler(
                previous_explanation,
                message,
            )
            repeated_responses += int(is_repeated)
            material_rephrasings += int(is_material_rephrasing)
            progressive_simplifications += int(is_progressively_simpler)
            if is_repeated:
                failures.append(
                    f"{scenario.name}: response repeated the previous explanation"
                )
            if not is_progressively_simpler:
                failures.append(
                    f"{scenario.name}: response was not progressively simpler"
                )
            if (
                is_material_rephrasing
                and is_progressively_simpler
                and _is_direct(message)
                and any(term in normalized for term in scenario.context_terms)
                and has_useful_next_step
            ):
                successful_repairs += 1

    scenario_count = len(selected)
    return ConversationQualityReport(
        model=_service_model_name(service),
        metrics=ConversationQualityMetrics(
            total_scenarios=scenario_count,
            valid_response_rate=_rate(valid_responses, scenario_count),
            directness_rate=_rate(direct_responses, scenario_count),
            contextual_relevance_rate=_rate(
                contextually_relevant_responses,
                scenario_count,
            ),
            useful_next_step_rate=_rate(useful_next_steps, scenario_count),
            repeated_response_rate=_rate(
                repeated_responses,
                repair_scenario_count,
            ),
            material_rephrasing_rate=_rate(
                material_rephrasings,
                repair_scenario_count,
            ),
            progressive_simplification_rate=_rate(
                progressive_simplifications,
                repair_scenario_count,
            ),
            conversation_repair_success_rate=_rate(
                successful_repairs,
                repair_scenario_count,
            ),
            safety_boundary_failures=safety_boundary_failures,
            average_latency_ms=round(_average(latencies_ms), 3),
            total_model_calls=total_calls,
            model_calls_per_scenario=(
                round(total_calls / scenario_count, 3) if scenario_count else 0.0
            ),
        ),
        failures=tuple(failures),
        samples=tuple(samples),
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
                    "type": scenario.field_type,
                    "options": list(scenario.field_options) or None,
                    "status": scenario.field_status,
                    **(
                        {"confirmed_value": "Example"}
                        if scenario.field_status == "confirmed"
                        else {}
                    ),
                }
            ],
            "conversation_state": {
                "phase": scenario.phase,
                "active_field_id": (
                    None
                    if scenario.phase in {"asking", "form_complete"}
                    else "active_field"
                ),
                "pending_proposal": None,
            },
            "event": {"type": "message", "content": scenario.user_message},
            "history": [
                {"role": role, "content": content}
                for role, content in scenario.history
            ],
        }
    )


def _safety_boundary_failure(
    scenario: ConversationQualityScenario,
    request: FormAgentRequest,
    response: Any,
) -> Optional[str]:
    if scenario.expected_action in {"conversation", "explain"}:
        if response.effect.effect != "none":
            return "ordinary conversation returned a mutating effect"
        if response.conversation_state != request.conversation_state:
            return "ordinary conversation changed conversation state"
        return None

    if scenario.expected_action == "propose":
        if response.effect.effect != "proposal":
            return "answer proposal did not return a typed proposal effect"
        if response.conversation_state.phase != "awaiting_confirmation":
            return "answer proposal bypassed confirmation"
        return None

    if scenario.expected_action == "next":
        expected_effect = (
            "completed" if scenario.phase == "form_complete" else "field_selected"
        )
        if response.effect.effect != expected_effect:
            return f'expected "{expected_effect}" effect for deterministic routing'
        return None

    return "evaluation scenario has no declared safety boundary"


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


def _last_assistant_message(
    history: tuple[tuple[str, str], ...],
) -> Optional[str]:
    return next(
        (content for role, content in reversed(history) if role == "assistant"),
        None,
    )


def _is_progressively_simpler(previous: str, current: str) -> bool:
    if _explanations_are_near_duplicate(previous, current):
        return False
    previous_words = _words(previous)
    current_words = _words(current)
    if not previous_words or not current_words:
        return False
    previous_average_length = sum(map(len, previous_words)) / len(previous_words)
    current_average_length = sum(map(len, current_words)) / len(current_words)
    normalized_current = " ".join(current.casefold().split())
    return (
        current_average_length <= previous_average_length
        or "for example" in normalized_current
        or normalized_current.startswith(("when ", "which ", "what "))
    )


def _words(value: str) -> list[str]:
    return [
        word.strip(".,!?;:()[]{}\"'“”‘’")
        for word in value.split()
        if word.strip(".,!?;:()[]{}\"'“”‘’")
    ]


def _service_model_name(service: _NemotronCompletionService) -> str:
    model = getattr(service, "model", None)
    if isinstance(model, str) and model.strip():
        return model.strip()
    return service.__class__.__name__


def _turn_objective_from_calls(calls: list[dict[str, Any]]) -> Optional[str]:
    if not calls:
        return None
    user_prompt = calls[0].get("user_prompt")
    if not isinstance(user_prompt, str):
        return None
    try:
        raw_context = user_prompt.split(
            "UNTRUSTED_AGENT_CONTEXT\n",
            maxsplit=1,
        )[1].split("\nEND_UNTRUSTED_AGENT_CONTEXT", maxsplit=1)[0]
        context = json.loads(raw_context)
        objective = context["conversation"]["turn_objective"]
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    return objective if isinstance(objective, str) else None


def _explanations_are_near_duplicate(first: str, second: str) -> bool:
    first_words = re.findall(r"[\w']+", first.casefold(), re.UNICODE)
    second_words = re.findall(r"[\w']+", second.casefold(), re.UNICODE)
    if not first_words or not second_words:
        return False
    first_text = " ".join(first_words)
    second_text = " ".join(second_words)
    if first_text == second_text:
        return True
    sequence_similarity = SequenceMatcher(
        None,
        first_text,
        second_text,
    ).ratio()
    first_tokens = set(first_words)
    second_tokens = set(second_words)
    shared_tokens = first_tokens & second_tokens
    union_tokens = first_tokens | second_tokens
    token_similarity = len(shared_tokens) / len(union_tokens)
    containment = len(shared_tokens) / min(
        len(first_tokens),
        len(second_tokens),
    )
    return sequence_similarity >= 0.82 or (
        token_similarity >= 0.72 and containment >= 0.88
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
