from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Iterable

from .models import ComparisonReport, MetricDelta, SuiteReport


_METRIC_DIRECTIONS = {
    "completed_turn_rate": "higher_is_better",
    "form_state_accuracy": "higher_is_better",
    "context_retention_rate": "higher_is_better",
    "unnecessary_repetition_rate": "lower_is_better",
    "clarification_quality": "higher_is_better",
    "recovery_success_rate": "higher_is_better",
    "heuristic_naturalness": "higher_is_better",
    "invention_failures": "lower_is_better",
    "deterministic_failure_count": "lower_is_better",
    "qualitative_failure_count": "lower_is_better",
    "average_turn_latency_ms": "lower_is_better",
}


def save_suite_report(
    report: SuiteReport,
    output_directory: Path,
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = report.run_id
    json_path = output_directory / f"{stem}.json"
    markdown_path = output_directory / f"{stem}.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_suite_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def load_report(path: Path) -> SuiteReport:
    return SuiteReport.model_validate_json(path.read_text(encoding="utf-8"))


def compare_suite_reports(
    baseline: SuiteReport,
    candidate: SuiteReport,
) -> ComparisonReport:
    baseline_metrics = baseline.metrics.model_dump(mode="json")
    candidate_metrics = candidate.metrics.model_dump(mode="json")
    deltas: dict[str, MetricDelta] = {}
    for name, direction in _METRIC_DIRECTIONS.items():
        before = baseline_metrics.get(name)
        after = candidate_metrics.get(name)
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            continue
        deltas[name] = MetricDelta(
            baseline=float(before),
            candidate=float(after),
            delta=round(float(after) - float(before), 3),
            direction=direction,  # type: ignore[arg-type]
        )

    baseline_failures = set(_failure_keys(baseline))
    candidate_failures = set(_failure_keys(candidate))
    return ComparisonReport(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        comparable_suite=baseline.suite_digest == candidate.suite_digest,
        metric_deltas=deltas,
        fixed_failures=sorted(baseline_failures - candidate_failures),
        new_failures=sorted(candidate_failures - baseline_failures),
        unchanged_failures=sorted(baseline_failures & candidate_failures),
    )


def save_comparison(report: ComparisonReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return output_path


def _failure_keys(report: SuiteReport) -> Iterable[str]:
    for scenario in report.scenarios:
        for failure in scenario.deterministic_failures:
            yield f"{scenario.scenario_id}: {_stable_failure_key(failure)}"
        if scenario.qualitative_assessment is not None:
            if scenario.qualitative_assessment.invents_information:
                yield f"{scenario.scenario_id} [qualitative]: invented information"
        if scenario.qualitative_error is not None:
            yield f"{scenario.scenario_id} [judge]: qualitative assessment failed"


def _stable_failure_key(failure: str) -> str:
    turn_match = re.match(r"turn \d+ \(([^)]+)\): (.+)", failure)
    if turn_match:
        turn_id, detail = turn_match.groups()
        categories = (
            "expected effect in",
            "expected phase",
            "expected prepared value",
            "expected effect field",
            "expected the conversation state",
            "assistant message did not include",
            "The application interface did not return",
            "proposal",
            "assistant introduced",
        )
        category = next(
            (candidate for candidate in categories if detail.startswith(candidate)),
            detail.split(":", maxsplit=1)[0],
        )
        return f"turn {turn_id}: {category}"
    if failure.startswith("final field "):
        field = failure.split(":", maxsplit=1)[0]
        return f"{field}: unexpected final state"
    if failure.startswith("conversation stopped after"):
        return "conversation stopped before all scheduled turns"
    return failure


def _suite_markdown(report: SuiteReport) -> str:
    metrics = report.metrics
    lines = [
        f"# Conversation evaluation: {report.label}",
        "",
        f"- Run: `{report.run_id}`",
        f"- Created: {report.created_at}",
        f"- Git revision: `{report.git_revision or 'unavailable'}`",
        f"- Target: {report.target}",
        f"- Model: `{report.model}`",
        f"- Judge: `{report.judge_model or 'not enabled'}`",
        f"- Suite: `{report.suite_id}` (`{report.suite_digest}`)",
        "",
        "## Metrics",
        "",
        f"- Form-state accuracy: {metrics.form_state_accuracy:.3f}",
        f"- Context retention: {metrics.context_retention_rate:.3f}",
        f"- Unnecessary repetition: {metrics.unnecessary_repetition_rate:.3f}",
        f"- Clarification quality: {metrics.clarification_quality:.3f}/5",
        f"- Recovery success: {metrics.recovery_success_rate:.3f}",
        f"- Heuristic naturalness: {metrics.heuristic_naturalness:.3f}/5",
        f"- Judged naturalness: {_optional_metric(metrics.judged_naturalness)}",
        f"- Invention failures: {metrics.invention_failures}",
        f"- Deterministic failures: {metrics.deterministic_failure_count}",
        f"- Average turn latency: {metrics.average_turn_latency_ms:.3f} ms",
        "",
    ]
    for scenario in report.scenarios:
        lines.extend(
            [
                f"## {scenario.title}",
                "",
                f"Persona: **{scenario.persona.name}** — {scenario.persona.summary}",
                "",
                f"Purpose: {scenario.purpose}",
                "",
                "### Failures",
                "",
            ]
        )
        if scenario.deterministic_failures:
            lines.extend(
                f"- {failure}" for failure in scenario.deterministic_failures
            )
        else:
            lines.append("- None")
        if scenario.qualitative_assessment is not None:
            assessment = scenario.qualitative_assessment
            lines.extend(
                [
                    "",
                    "### Qualitative assessment",
                    "",
                    assessment.summary,
                    "",
                    f"Naturalness {assessment.naturalness}/5; context "
                    f"{assessment.context_awareness}/5; invents information: "
                    f"{assessment.invents_information}.",
                ]
            )
            lines.extend(
                f"- {failure}" for failure in assessment.failure_reasons
            )
        elif scenario.qualitative_error is not None:
            lines.extend(["", f"Judge error: {scenario.qualitative_error}"])

        lines.extend(["", "### Transcript", ""])
        for turn in scenario.transcript:
            user_text = turn.visible_user_message or _event_label(turn.user_event)
            assistant_text = turn.assistant_message or turn.error or "No response"
            lines.extend(
                [
                    f"**User:** {user_text}",
                    "",
                    f"**Assistant:** {assistant_text}",
                    "",
                    f"Effect: `{json.dumps(turn.response_effect, ensure_ascii=False)}`",
                    "",
                ]
            )
        lines.extend(
            [
                "### Expected and actual form state",
                "",
                "```json",
                json.dumps(
                    {
                        "expected": scenario.expected_final_state.model_dump(
                            mode="json"
                        ),
                        "actual": scenario.actual_form_state,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _event_label(event: dict[str, object]) -> str:
    return f"[{event.get('type', 'unknown')} event]"


def _optional_metric(value: float | None) -> str:
    return "not scored" if value is None else f"{value:.3f}/5"
