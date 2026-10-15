from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.services.form_agent import FormAgentService
from app.services.nemotron_service import (
    NemotronConfigurationError,
    NemotronService,
)
from app.services.tavily_service import TavilyService

from .judge import NemotronPairwiseJudge, NemotronQualitativeJudge
from .reporting import (
    compare_suite_reports,
    load_report,
    save_comparison,
    save_pairwise_comparison,
    save_suite_report,
)
from .runner import run_pairwise_comparison, run_suite
from .scenarios import (
    DEFAULT_SCENARIO_PATH,
    load_scenario_suite,
    scenario_file_digest,
)
from .targets import HttpConversationTarget, ServiceConversationTarget


DEFAULT_RESULTS_PATH = Path(__file__).parents[1] / "results"


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    if args.command == "run":
        raise SystemExit(asyncio.run(_run(args)))
    if args.command == "compare":
        raise SystemExit(_compare(args))
    if args.command == "pairwise":
        raise SystemExit(asyncio.run(_pairwise(args)))
    parser.error("A command is required")


async def _run(args: argparse.Namespace) -> int:
    scenario_path = args.scenarios.resolve()
    suite = load_scenario_suite(scenario_path)
    try:
        judge_service = NemotronService.from_environment() if args.judge else None
        if args.target == "local":
            model_service = judge_service or NemotronService.from_environment()
            target = ServiceConversationTarget(
                FormAgentService(
                    model_service,
                    TavilyService.from_optional_environment(),
                ),
                model=model_service.model,
            )
        else:
            target = HttpConversationTarget(args.base_url)
    except NemotronConfigurationError as error:
        print(f"Configuration error: {error}")
        return 2

    judge = (
        NemotronQualitativeJudge(judge_service)
        if judge_service is not None
        else None
    )
    report = await run_suite(
        suite,
        target,
        label=args.label,
        judge=judge,
        suite_digest=scenario_file_digest(scenario_path),
    )
    json_path, markdown_path = save_suite_report(report, args.output_dir)
    print(json.dumps(report.metrics.model_dump(mode="json"), indent=2))
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 0


def _compare(args: argparse.Namespace) -> int:
    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)
    comparison = compare_suite_reports(baseline, candidate)
    print(json.dumps(comparison.model_dump(mode="json"), indent=2))
    if args.output is not None:
        print(f"Comparison report: {save_comparison(comparison, args.output)}")
    return 0 if comparison.comparable_suite else 2


async def _pairwise(args: argparse.Namespace) -> int:
    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)
    if baseline.suite_digest != candidate.suite_digest:
        print("Reports use different scenario-suite digests")
        return 2
    try:
        service = NemotronService.from_environment()
    except NemotronConfigurationError as error:
        print(f"Configuration error: {error}")
        return 2
    report = await run_pairwise_comparison(
        baseline,
        candidate,
        NemotronPairwiseJudge(service),
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2))
    if args.output is not None:
        print(
            "Pairwise report: "
            f"{save_pairwise_comparison(report, args.output)}"
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run and compare complete Form Agent conversation evaluations"
    )
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="run the full scenario suite")
    run_parser.add_argument("--label", default="baseline")
    run_parser.add_argument(
        "--scenarios",
        type=Path,
        default=DEFAULT_SCENARIO_PATH,
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_PATH,
    )
    run_parser.add_argument(
        "--target",
        choices=("local", "http"),
        default="local",
        help="call FormAgentService in-process or POST to a running API",
    )
    run_parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API base URL used with --target http",
    )
    run_parser.add_argument(
        "--judge",
        action="store_true",
        help="add a Nemotron qualitative rubric to deterministic scoring",
    )

    compare_parser = subparsers.add_parser(
        "compare", help="compare two saved JSON reports"
    )
    compare_parser.add_argument("baseline", type=Path)
    compare_parser.add_argument("candidate", type=Path)
    compare_parser.add_argument("--output", type=Path)

    pairwise_parser = subparsers.add_parser(
        "pairwise",
        help="blindly compare matching baseline and candidate transcripts",
    )
    pairwise_parser.add_argument("baseline", type=Path)
    pairwise_parser.add_argument("candidate", type=Path)
    pairwise_parser.add_argument("--output", type=Path)
    return parser


if __name__ == "__main__":
    main()
