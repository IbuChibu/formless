from __future__ import annotations

import re
import subprocess
from typing import Optional

from .judge import NemotronQualitativeJudge
from .models import (
    ComparisonReport,
    ScenarioReport,
    ScenarioSuite,
    SuiteMetrics,
    SuiteReport,
)
from .reporting import compare_suite_reports
from .scenarios import scenario_suite_digest
from .simulator import ConversationSimulator
from .targets import ConversationTarget


async def run_suite(
    suite: ScenarioSuite,
    target: ConversationTarget,
    *,
    label: str,
    judge: Optional[NemotronQualitativeJudge] = None,
    suite_digest: Optional[str] = None,
) -> SuiteReport:
    personas = {persona.id: persona for persona in suite.personas}
    simulator = ConversationSimulator(target)
    scenario_reports: list[ScenarioReport] = []
    for scenario in suite.scenarios:
        report = await simulator.run(scenario, personas[scenario.persona_id])
        if judge is not None:
            try:
                assessment = await judge.assess(report)
            except Exception as error:  # Preserve a baseline even if judging fails.
                report = report.model_copy(
                    update={
                        "qualitative_error": f"{error.__class__.__name__}: {error}"
                    }
                )
            else:
                report = report.model_copy(
                    update={"qualitative_assessment": assessment}
                )
        scenario_reports.append(report)

    created_at = SuiteReport.timestamp()
    run_stamp = re.sub(r"[^0-9]", "", created_at)[:20]
    safe_label = re.sub(r"[^a-z0-9-]+", "-", label.casefold()).strip("-")
    run_id = f"{run_stamp}-{safe_label or 'evaluation'}"
    return SuiteReport(
        run_id=run_id,
        label=label,
        created_at=created_at,
        git_revision=_git_revision(),
        suite_id=suite.suite_id,
        suite_digest=suite_digest or scenario_suite_digest(suite),
        target=target.name,
        model=target.model,
        judge_model=judge.model if judge is not None else None,
        metrics=_aggregate_metrics(suite, scenario_reports),
        scenarios=scenario_reports,
    )


def compare_reports(
    baseline: SuiteReport,
    candidate: SuiteReport,
) -> ComparisonReport:
    return compare_suite_reports(baseline, candidate)


def _aggregate_metrics(
    suite: ScenarioSuite,
    reports: list[ScenarioReport],
) -> SuiteMetrics:
    expected_turns = sum(len(scenario.turns) for scenario in suite.scenarios)
    completed_turns = sum(
        turn.error is None for report in reports for turn in report.transcript
    )
    all_turns = [turn for report in reports for turn in report.transcript]
    context_scores = [
        report.scores.context_retention
        for report in reports
        if report.scores.context_retention is not None
    ]
    clarification_scores = [
        report.scores.clarification_quality
        for report in reports
        if report.scores.clarification_quality is not None
    ]
    recovery_scores = [
        report.scores.recovery_success
        for report in reports
        if report.scores.recovery_success is not None
    ]
    assessments = [
        report.qualitative_assessment
        for report in reports
        if report.qualitative_assessment is not None
    ]
    judged_clarifications = [
        assessment.clarification_quality
        for assessment in assessments
        if assessment.clarification_quality is not None
    ]
    judged_recoveries = [
        assessment.recovery_quality
        for assessment in assessments
        if assessment.recovery_quality is not None
    ]
    qualitative_failures = sum(
        len(assessment.failure_reasons) + int(assessment.invents_information)
        for assessment in assessments
    ) + sum(report.qualitative_error is not None for report in reports)
    return SuiteMetrics(
        scenario_count=len(reports),
        turn_count=len(all_turns),
        completed_turn_rate=_rate(completed_turns, expected_turns),
        form_state_accuracy=_average(
            [report.scores.form_state_accuracy for report in reports]
        ),
        context_retention_rate=_average(context_scores),
        unnecessary_repetition_rate=_average(
            [report.scores.unnecessary_repetition_rate for report in reports]
        ),
        clarification_quality=_average(clarification_scores),
        recovery_success_rate=_average(recovery_scores),
        heuristic_naturalness=_average(
            [report.scores.heuristic_naturalness for report in reports]
        ),
        judged_naturalness=_optional_average(
            [float(assessment.naturalness) for assessment in assessments]
        ),
        judged_context_awareness=_optional_average(
            [float(assessment.context_awareness) for assessment in assessments]
        ),
        judged_clarification_quality=_optional_average(
            [float(value) for value in judged_clarifications]
        ),
        judged_recovery_quality=_optional_average(
            [float(value) for value in judged_recoveries]
        ),
        invention_failures=sum(
            report.scores.invention_failures for report in reports
        ),
        deterministic_failure_count=sum(
            len(report.deterministic_failures) for report in reports
        ),
        qualitative_failure_count=qualitative_failures,
        average_turn_latency_ms=_average([turn.latency_ms for turn in all_turns]),
    )


def _git_revision() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 1.0


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _optional_average(values: list[float]) -> Optional[float]:
    return _average(values) if values else None
