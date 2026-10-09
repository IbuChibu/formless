import asyncio

from evaluations.form_agent_evaluation import (
    evaluation_scenarios,
    run_evaluation,
)


def test_offline_evaluation_covers_supported_fixtures_and_boundaries() -> None:
    report = asyncio.run(run_evaluation())

    assert {scenario.fixture for scenario in evaluation_scenarios()} == {
        "sample_form.pdf",
        "household_support_review_demo.pdf",
        "real_world/uscis_i9_2025.pdf",
        "real_world/sba_startup_costs_2023.pdf",
    }
    assert report.failures == ()
    assert report.metrics.total_scenarios == 14
    assert report.metrics.fixture_count == 4
    assert report.metrics.valid_action_rate == 1.0
    assert report.metrics.grounded_question_selection_rate == 1.0
    assert report.metrics.valid_proposal_rate == 1.0
    assert report.metrics.invented_fact_failures == 0
    assert report.metrics.invented_purpose_failures == 0
    assert report.metrics.confirmation_boundary_failures == 0
