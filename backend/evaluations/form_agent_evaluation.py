from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, Optional

from pydantic import ValidationError

from app.services.form_agent_service import (
    FormAgentAction,
    FormAgentError,
    FormAgentField,
    FormAgentFormContext,
    FormAgentMessage,
    FormAgentRequest,
    FormAgentService,
    ProposeAction,
)
from app.services.nemotron_service import (
    NemotronConfigurationError,
    NemotronService,
    NemotronServiceError,
)
from app.services.pdf_service import PdfField, extract_acroform


FIXTURES_PATH = Path(__file__).parents[1] / "tests" / "fixtures"
SUPPORTED_FIELD_TYPES = {
    "text",
    "textarea",
    "number",
    "dropdown",
    "checkbox",
}
_PLACEHOLDER_OPTION_PATTERN = re.compile(
    r"^(?:please\s+)?(?:select|choose)(?:\s+(?:one|an?\s+option))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvaluationScenario:
    name: str
    fixture: str
    active_field_id: Optional[str]
    message: str
    model_response: str
    expected_action: str
    expected_field_id: str
    expected_value: Optional[str | bool] = None
    expected_question: Optional[str] = None
    purpose_safety_check: bool = False
    history: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class EvaluationMetrics:
    total_scenarios: int
    fixture_count: int
    valid_action_rate: float
    grounded_question_selection_rate: float
    valid_proposal_rate: float
    invented_fact_failures: int
    invented_purpose_failures: int
    confirmation_boundary_failures: int


@dataclass(frozen=True)
class EvaluationReport:
    metrics: EvaluationMetrics
    failures: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "metrics": asdict(self.metrics),
            "failures": list(self.failures),
        }


class _ScriptedNemotronService:
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 600,
        json_response: bool = False,
    ) -> str:
        return self._response


def evaluation_scenarios() -> tuple[EvaluationScenario, ...]:
    return (
        EvaluationScenario(
            name="sample-grounded-next",
            fixture="sample_form.pdf",
            active_field_id=None,
            message="Start the form.",
            model_response=(
                '{"action":"next","message":"Start",'
                '"field_id":"full_name"}'
            ),
            expected_action="next",
            expected_field_id="full_name",
            expected_question="Full name",
        ),
        EvaluationScenario(
            name="household-grounded-next",
            fixture="household_support_review_demo.pdf",
            active_field_id=None,
            message="Start the form.",
            model_response=(
                '{"action":"next","message":"Start",'
                '"field_id":"applicant_full_legal_name"}'
            ),
            expected_action="next",
            expected_field_id="applicant_full_legal_name",
            expected_question="Full legal name",
        ),
        EvaluationScenario(
            name="i9-grounded-next",
            fixture="real_world/uscis_i9_2025.pdf",
            active_field_id=None,
            message="Start the form.",
            model_response=(
                '{"action":"next","message":"Start",'
                '"field_id":"Last Name (Family Name)"}'
            ),
            expected_action="next",
            expected_field_id="Last Name (Family Name)",
            expected_question="Last Name (Family Name)",
        ),
        EvaluationScenario(
            name="sba-grounded-next",
            fixture="real_world/sba_startup_costs_2023.pdf",
            active_field_id=None,
            message="Start the worksheet.",
            model_response=(
                '{"action":"next","message":"Start",'
                '"field_id":"Monthly rent expense 1"}'
            ),
            expected_action="next",
            expected_field_id="Monthly rent expense 1",
            expected_question="Rent Budget item 1, edit to change item",
        ),
        EvaluationScenario(
            name="sample-text-proposal",
            fixture="sample_form.pdf",
            active_field_id="full_name",
            message="My full name is Ada Example.",
            model_response=(
                '{"action":"propose","message":"Proposal",'
                '"field_id":"full_name","value":"Ada Example"}'
            ),
            expected_action="propose",
            expected_field_id="full_name",
            expected_value="Ada Example",
        ),
        EvaluationScenario(
            name="household-dropdown-proposal",
            fixture="household_support_review_demo.pdf",
            active_field_id="primary_support_category",
            message="Housing stability.",
            model_response=(
                '{"action":"propose","message":"Proposal",'
                '"field_id":"primary_support_category",'
                '"value":"housing stability"}'
            ),
            expected_action="propose",
            expected_field_id="primary_support_category",
            expected_value="Housing stability",
        ),
        EvaluationScenario(
            name="household-checkbox-proposal",
            fixture="household_support_review_demo.pdf",
            active_field_id="shares_food_or_living_costs",
            message="Yes, I do.",
            model_response=(
                '{"action":"propose","message":"Proposal",'
                '"field_id":"shares_food_or_living_costs","value":"yes"}'
            ),
            expected_action="propose",
            expected_field_id="shares_food_or_living_costs",
            expected_value=True,
        ),
        EvaluationScenario(
            name="i9-dropdown-proposal",
            fixture="real_world/uscis_i9_2025.pdf",
            active_field_id="State",
            message="California, CA.",
            model_response=(
                '{"action":"propose","message":"Proposal",'
                '"field_id":"State","value":"ca"}'
            ),
            expected_action="propose",
            expected_field_id="State",
            expected_value="CA",
        ),
        EvaluationScenario(
            name="sba-number-proposal",
            fixture="real_world/sba_startup_costs_2023.pdf",
            active_field_id="One-time budget cost 1",
            message="The budget amount is 1250.",
            model_response=(
                '{"action":"propose","message":"Proposal",'
                '"field_id":"One-time budget cost 1","value":1250}'
            ),
            expected_action="propose",
            expected_field_id="One-time budget cost 1",
            expected_value="1250",
        ),
        EvaluationScenario(
            name="household-skip-boundary",
            fixture="household_support_review_demo.pdf",
            active_field_id="primary_support_category",
            message="Skip this for now.",
            model_response=(
                '{"action":"skip","message":"Skipped",'
                '"field_id":"primary_support_category"}'
            ),
            expected_action="skip",
            expected_field_id="primary_support_category",
        ),
        EvaluationScenario(
            name="i9-follow-up-explanation",
            fixture="real_world/uscis_i9_2025.pdf",
            active_field_id="Last Name (Family Name)",
            message="What does family name mean here?",
            model_response=(
                '{"action":"explain","message":"Use the last name shown '
                'on the employee record.",'
                '"field_id":"Last Name (Family Name)"}'
            ),
            expected_action="explain",
            expected_field_id="Last Name (Family Name)",
            history=(
                ("assistant", "Last Name (Family Name)"),
                ("user", "What does family name mean here?"),
            ),
        ),
        EvaluationScenario(
            name="sample-purpose-safety",
            fixture="sample_form.pdf",
            active_field_id="full_name",
            message="Why does the organisation require this?",
            model_response="{}",
            expected_action="explain",
            expected_field_id="full_name",
            purpose_safety_check=True,
        ),
    )


async def run_evaluation(
    live_service: Optional[NemotronService] = None,
) -> EvaluationReport:
    scenarios = evaluation_scenarios()
    failures = []
    valid_actions = 0
    grounded_checks = 0
    grounded_successes = 0
    proposal_checks = 0
    valid_proposals = 0
    invented_fact_failures = 0
    invented_purpose_failures = 0
    confirmation_boundary_failures = 0

    for scenario in scenarios:
        request = _request_for_scenario(scenario)
        service = live_service or _ScriptedNemotronService(
            scenario.model_response
        )
        try:
            action = await FormAgentService(service).respond(  # type: ignore[arg-type]
                request
            )
        except (FormAgentError, NemotronServiceError) as error:
            failures.append(f"{scenario.name}: {error}")
            continue

        action_is_valid = (
            action.action == scenario.expected_action
            and action.field_id == scenario.expected_field_id
        )
        if action_is_valid:
            valid_actions += 1
        else:
            failures.append(
                f"{scenario.name}: expected {scenario.expected_action} on "
                f"{scenario.expected_field_id}, got {action.action} on "
                f"{action.field_id}"
            )

        if scenario.expected_question is not None:
            grounded_checks += 1
            if scenario.expected_question in action.message:
                grounded_successes += 1
            else:
                failures.append(
                    f"{scenario.name}: grounded question was not selected"
                )

        if scenario.expected_action == "propose":
            proposal_checks += 1
            if (
                isinstance(action, ProposeAction)
                and action.field_id == scenario.expected_field_id
                and action.value == scenario.expected_value
            ):
                valid_proposals += 1
            else:
                invented_fact_failures += int(
                    isinstance(action, ProposeAction)
                    and action.value != scenario.expected_value
                )

            normalized_message = action.message.casefold()
            if not (
                "awaiting your confirmation" in normalized_message
                and "not been applied" in normalized_message
            ):
                confirmation_boundary_failures += 1
        elif isinstance(action, ProposeAction):
            invented_fact_failures += 1

        if scenario.purpose_safety_check:
            normalized_message = action.message.casefold()
            if not (
                "authoritative reason" in normalized_message
                and "official instructions" in normalized_message
            ):
                invented_purpose_failures += 1

    metrics = EvaluationMetrics(
        total_scenarios=len(scenarios),
        fixture_count=len({scenario.fixture for scenario in scenarios}),
        valid_action_rate=_rate(valid_actions, len(scenarios)),
        grounded_question_selection_rate=_rate(
            grounded_successes,
            grounded_checks,
        ),
        valid_proposal_rate=_rate(valid_proposals, proposal_checks),
        invented_fact_failures=invented_fact_failures,
        invented_purpose_failures=invented_purpose_failures,
        confirmation_boundary_failures=confirmation_boundary_failures,
    )
    return EvaluationReport(metrics=metrics, failures=tuple(failures))


def _request_for_scenario(scenario: EvaluationScenario) -> FormAgentRequest:
    extraction = extract_acroform(
        (FIXTURES_PATH / scenario.fixture).read_bytes()
    )
    fields = [
        agent_field
        for field in extraction.fields
        if (agent_field := _agent_field(field)) is not None
    ]
    return FormAgentRequest(
        form_context=FormAgentFormContext(
            title=extraction.form_context.title,
            instructions=list(extraction.form_context.instructions),
        ),
        fields=fields,
        active_field_id=scenario.active_field_id,
        message=scenario.message,
        history=[
            FormAgentMessage(role=role, content=content)  # type: ignore[arg-type]
            for role, content in scenario.history
        ],
    )


def _agent_field(field: PdfField) -> Optional[FormAgentField]:
    if field.type not in SUPPORTED_FIELD_TYPES:
        return None
    try:
        options = [
            option
            for option in (field.options or [])
            if not _is_placeholder_option(option)
        ]
        if field.type == "dropdown" and not options:
            return None
        return FormAgentField(
            id=field.id,
            label=field.label,
            question=field.question,
            help_text=field.help_text,
            section=field.section,
            page_context=field.page_context,
            type=field.type,  # type: ignore[arg-type]
            page=field.page,
            options=options or None,
            status="unanswered",
        )
    except ValidationError:
        return None


def _is_placeholder_option(option: str) -> bool:
    normalized = option.strip().strip("-–—_:.…").strip()
    return not normalized or _PLACEHOLDER_OPTION_PATTERN.fullmatch(normalized) is not None


def _rate(successes: int, checks: int) -> float:
    return round(successes / checks, 3) if checks else 1.0


async def _run_cli(live: bool) -> int:
    live_service = None
    if live:
        try:
            live_service = NemotronService.from_environment()
        except NemotronConfigurationError as error:
            print(str(error))
            return 2

    report = await run_evaluation(live_service)
    print(json.dumps(report.as_dict(), indent=2))
    return 0 if not report.failures else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Form Agent behavior across supported PDF fixtures."
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
