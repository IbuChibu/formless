from __future__ import annotations

import re
import subprocess
import hashlib
from typing import Optional

from .judge import NemotronPairwiseJudge, NemotronQualitativeJudge
from .models import (
    ComparisonReport,
    PairwiseComparisonReport,
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
    metrics = _aggregate_metrics(suite, scenario_reports)
    correctness_failures = _correctness_gate_failures(metrics)
    human_helper_failures = _human_helper_gate_failures(metrics)
    metrics = metrics.model_copy(
        update={
            "correctness_gate_passed": not correctness_failures,
            "human_helper_gate_passed": not human_helper_failures,
        }
    )
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
        metrics=metrics,
        scenarios=scenario_reports,
        correctness_gate_failures=correctness_failures,
        human_helper_gate_failures=human_helper_failures,
    )


def compare_reports(
    baseline: SuiteReport,
    candidate: SuiteReport,
) -> ComparisonReport:
    return compare_suite_reports(baseline, candidate)


async def run_pairwise_comparison(
    baseline: SuiteReport,
    candidate: SuiteReport,
    judge: NemotronPairwiseJudge,
) -> PairwiseComparisonReport:
    if baseline.suite_digest != candidate.suite_digest:
        return PairwiseComparisonReport(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            comparable_suite=False,
            judge_model=judge.model,
            candidate_wins=0,
            baseline_wins=0,
            ties=0,
            assessments=[],
        )
    candidate_by_id = {
        report.scenario_id: report for report in candidate.scenarios
    }
    if set(candidate_by_id) != {
        report.scenario_id for report in baseline.scenarios
    }:
        raise ValueError("Comparable reports must contain the same scenarios")
    assessments = []
    for baseline_report in baseline.scenarios:
        digest = hashlib.sha256(
            baseline_report.scenario_id.encode("utf-8")
        ).digest()
        assessments.append(
            await judge.assess(
                baseline_report,
                candidate_by_id[baseline_report.scenario_id],
                candidate_first=bool(digest[0] % 2),
            )
        )
    return PairwiseComparisonReport(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        comparable_suite=True,
        judge_model=judge.model,
        candidate_wins=sum(item.preferred == "candidate" for item in assessments),
        baseline_wins=sum(item.preferred == "baseline" for item in assessments),
        ties=sum(item.preferred == "tie" for item in assessments),
        assessments=assessments,
    )


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
    latest_answer_scores = [
        report.scores.latest_answer_adherence
        for report in reports
        if report.scores.latest_answer_adherence is not None
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
    judged_human_helper = [
        assessment.human_helper_resemblance
        for assessment in assessments
        if assessment.human_helper_resemblance is not None
    ]
    qualitative_failures = sum(
        len(assessment.failure_reasons) + int(assessment.invents_information)
        for assessment in assessments
    ) + sum(report.qualitative_error is not None for report in reports)
    confirmed_field_count = sum(
        report.scores.confirmed_field_count for report in reports
    )
    turns_per_confirmed_field = (
        round(len(all_turns) / confirmed_field_count, 3)
        if confirmed_field_count
        else None
    )
    expected_behavior_checks = sum(
        _behavior_expectation_count(turn.behavior)
        for scenario in suite.scenarios
        for turn in scenario.turns
    )
    completed_behavior_checks = sum(
        len(turn.behavior_results) for turn in all_turns
    )
    return SuiteMetrics(
        scenario_count=len(reports),
        turn_count=len(all_turns),
        completed_turn_rate=_rate(completed_turns, expected_turns),
        form_state_accuracy=_average(
            [report.scores.form_state_accuracy for report in reports]
        ),
        context_retention_rate=_optional_average(context_scores),
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
        latest_answer_adherence_rate=_optional_average(latest_answer_scores),
        contradiction_failure_count=sum(
            report.scores.contradiction_failures for report in reports
        ),
        volunteered_fact_recall_rate=_optional_average(
            _defined_scores(reports, "volunteered_fact_recall")
        ),
        redundant_question_rate=_optional_average(
            _defined_scores(reports, "redundant_question_rate")
        ),
        side_question_recovery_rate=_optional_average(
            _defined_scores(reports, "side_question_recovery")
        ),
        unnecessary_push_rate=_optional_average(
            _defined_scores(reports, "unnecessary_push_rate")
        ),
        speech_suitability_rate=_optional_average(
            _defined_scores(reports, "speech_suitability")
        ),
        acknowledgement_rate=_optional_average(
            _defined_scores(reports, "acknowledgement_rate")
        ),
        interruption_recovery_rate=_optional_average(
            _defined_scores(reports, "interruption_recovery")
        ),
        clarification_success_rate=_optional_average(
            _defined_scores(reports, "clarification_success")
        ),
        human_helper_behavior_rate=_optional_average(
            _defined_scores(reports, "human_helper_behavior_rate")
        ),
        behavior_check_coverage_rate=_rate(
            completed_behavior_checks,
            expected_behavior_checks,
        ),
        turns_per_confirmed_field=turns_per_confirmed_field,
        confirmation_boundary_failure_count=sum(
            report.scores.confirmation_boundary_failures for report in reports
        ),
        judged_human_helper_resemblance=_optional_average(
            [float(value) for value in judged_human_helper]
        ),
    )


def _defined_scores(
    reports: list[ScenarioReport],
    name: str,
) -> list[float]:
    values = [getattr(report.scores, name) for report in reports]
    return [float(value) for value in values if value is not None]


def _behavior_expectation_count(expectation: object) -> int:
    list_checks = (
        "answers_latest_request_with_any",
        "acknowledges_with_any",
        "returns_to_form_with_any",
        "clarifies_with_any",
        "forbidden_reask_terms",
    )
    count = sum(bool(getattr(expectation, name)) for name in list_checks)
    count += int(bool(getattr(expectation, "must_not_advance")))
    count += int(getattr(expectation, "max_questions") is not None)
    count += int(bool(getattr(expectation, "speech_suitable")))
    return count


def _correctness_gate_failures(metrics: SuiteMetrics) -> list[str]:
    failures: list[str] = []
    if metrics.completed_turn_rate < 1.0:
        failures.append("not every scheduled turn completed")
    if metrics.form_state_accuracy < 1.0:
        failures.append("expected canonical form state was not exact")
    if metrics.invention_failures:
        failures.append("one or more proposals or claims were ungrounded")
    if metrics.confirmation_boundary_failure_count:
        failures.append("the explicit confirmation boundary failed")
    if metrics.contradiction_failure_count:
        failures.append("assistant wording contradicted transcript or state")
    return failures


def _human_helper_gate_failures(metrics: SuiteMetrics) -> list[str]:
    failures: list[str] = []
    if metrics.behavior_check_coverage_rate < 1.0:
        failures.append("not every scheduled human-helper check was reached")
    minimum_rates = {
        "volunteered_fact_recall_rate": "volunteered facts were not retained",
        "side_question_recovery_rate": "side questions did not return smoothly",
        "speech_suitability_rate": "too many responses were unsuitable for speech",
        "acknowledgement_rate": "answers were not acknowledged clearly",
        "interruption_recovery_rate": "interruptions did not recover reliably",
        "clarification_success_rate": "clarifications did not resolve confusion",
        "human_helper_behavior_rate": "overall human-helper behaviour was weak",
    }
    for name, reason in minimum_rates.items():
        value = getattr(metrics, name)
        if value is not None and value < 0.8:
            failures.append(reason)
    if metrics.human_helper_behavior_rate is None:
        failures.append("no explicit human-helper behaviour was scored")
    if (
        metrics.redundant_question_rate is not None
        and metrics.redundant_question_rate > 0.1
    ):
        failures.append("the assistant re-asked known information too often")
    if metrics.unnecessary_push_rate is not None and metrics.unnecessary_push_rate > 0.1:
        failures.append("the assistant pushed the workflow unnecessarily")
    if (
        metrics.judged_human_helper_resemblance is not None
        and metrics.judged_human_helper_resemblance < 4.0
    ):
        failures.append("qualitative human-helper resemblance was below 4/5")
    return failures


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
