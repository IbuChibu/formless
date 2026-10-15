from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


FieldValue = Union[str, bool]


class HarnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Persona(HarnessModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    communication_style: str = Field(min_length=1)
    behaviours: list[str] = Field(min_length=1)


class TurnExpectation(HarnessModel):
    effects: list[str] = Field(default_factory=list)
    phase: Optional[str] = None
    field_id: Optional[str] = None
    prepared_value: Optional[FieldValue] = None
    state_unchanged: bool = False
    message_includes_any: list[str] = Field(default_factory=list)
    message_includes_all: list[str] = Field(default_factory=list)
    message_excludes_all: list[str] = Field(default_factory=list)
    max_assistant_words: Optional[int] = Field(default=None, ge=1, le=500)


class BehaviorExpectation(HarnessModel):
    """Observable conversation qualities without requiring one exact reply."""

    answers_latest_request_with_any: list[str] = Field(default_factory=list)
    acknowledges_with_any: list[str] = Field(default_factory=list)
    returns_to_form_with_any: list[str] = Field(default_factory=list)
    clarifies_with_any: list[str] = Field(default_factory=list)
    forbidden_reask_terms: list[str] = Field(default_factory=list)
    must_not_advance: bool = False
    max_questions: Optional[int] = Field(default=None, ge=0, le=5)
    speech_suitable: bool = False


class BranchCondition(HarnessModel):
    previous_effects: list[str] = Field(default_factory=list)
    previous_message_includes_any: list[str] = Field(default_factory=list)
    previous_message_excludes_all: list[str] = Field(default_factory=list)
    previous_expectation_failed: Optional[bool] = None


class TurnBranch(HarnessModel):
    id: str = Field(min_length=1)
    when: BranchCondition
    event: dict[str, Any]
    visible_user_message: Optional[str] = None


class ScenarioTurn(HarnessModel):
    id: str = Field(min_length=1)
    event: dict[str, Any]
    visible_user_message: Optional[str] = None
    tags: list[
        Literal[
            "clarification",
            "context_retention",
            "emotion",
            "recovery",
            "repetition_check",
            "latest_answer",
            "contradiction_check",
            "style_check",
            "acknowledgement",
            "side_question_recovery",
            "volunteered_fact_recall",
            "redundant_question_check",
            "unnecessary_push_check",
            "speech_suitability",
            "interruption_recovery",
            "clarification_success",
            "confirmation_boundary",
        ]
    ] = Field(default_factory=list)
    expect: TurnExpectation = Field(default_factory=TurnExpectation)
    behavior: BehaviorExpectation = Field(default_factory=BehaviorExpectation)
    branches: list[TurnBranch] = Field(default_factory=list)


class ExpectedFinalState(HarnessModel):
    confirmed_values: dict[str, FieldValue] = Field(default_factory=dict)
    skipped_field_ids: list[str] = Field(default_factory=list)
    unanswered_field_ids: list[str] = Field(default_factory=list)


class ConversationScenario(HarnessModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    persona_id: str = Field(min_length=1)
    fixture: str = Field(min_length=1)
    field_ids: list[str] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    turns: list[ScenarioTurn] = Field(min_length=1)
    initial_confirmed_values: dict[str, FieldValue] = Field(default_factory=dict)
    initial_skipped_field_ids: list[str] = Field(default_factory=list)
    expected_final: ExpectedFinalState
    allowed_proposals: dict[str, list[FieldValue]] = Field(default_factory=dict)
    forbidden_assistant_terms: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_declared_fields(self) -> ConversationScenario:
        declared = set(self.field_ids)
        referenced = (
            set(self.initial_confirmed_values)
            | set(self.initial_skipped_field_ids)
            | set(self.expected_final.confirmed_values)
            | set(self.expected_final.skipped_field_ids)
            | set(self.expected_final.unanswered_field_ids)
            | set(self.allowed_proposals)
        )
        unknown = sorted(referenced - declared)
        if unknown:
            raise ValueError(
                "Scenario state references undeclared fields: "
                + ", ".join(unknown)
            )
        return self


class ScenarioSuite(HarnessModel):
    schema_version: int = 1
    suite_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    personas: list[Persona] = Field(min_length=1)
    scenarios: list[ConversationScenario] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> ScenarioSuite:
        persona_ids = [persona.id for persona in self.personas]
        scenario_ids = [scenario.id for scenario in self.scenarios]
        if len(persona_ids) != len(set(persona_ids)):
            raise ValueError("Persona IDs must be unique")
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("Scenario IDs must be unique")
        unknown = sorted(
            {
                scenario.persona_id
                for scenario in self.scenarios
                if scenario.persona_id not in persona_ids
            }
        )
        if unknown:
            raise ValueError(
                "Scenarios reference unknown personas: " + ", ".join(unknown)
            )
        return self


class RecordedTurn(HarnessModel):
    id: str
    index: int
    tags: list[str]
    user_event: dict[str, Any]
    visible_user_message: Optional[str]
    request_state: dict[str, Any]
    fields_before: dict[str, dict[str, Any]]
    assistant_message: Optional[str] = None
    response_effect: Optional[dict[str, Any]] = None
    response_state: Optional[dict[str, Any]] = None
    fields_after: dict[str, dict[str, Any]]
    latency_ms: float
    expectation_failures: list[str] = Field(default_factory=list)
    behavior_results: dict[str, bool] = Field(default_factory=dict)
    behavior_failures: list[str] = Field(default_factory=list)
    selected_branch_id: Optional[str] = None
    error: Optional[str] = None


class QualitativeAssessment(HarnessModel):
    naturalness: int = Field(ge=1, le=5)
    context_awareness: int = Field(ge=1, le=5)
    clarification_quality: Optional[int] = Field(default=None, ge=1, le=5)
    recovery_quality: Optional[int] = Field(default=None, ge=1, le=5)
    attentiveness: Optional[int] = Field(default=None, ge=1, le=5)
    helpfulness: Optional[int] = Field(default=None, ge=1, le=5)
    conversational_flow: Optional[int] = Field(default=None, ge=1, le=5)
    adaptability: Optional[int] = Field(default=None, ge=1, le=5)
    user_effort: Optional[int] = Field(default=None, ge=1, le=5)
    human_helper_resemblance: Optional[int] = Field(default=None, ge=1, le=5)
    invents_information: bool
    summary: str = Field(min_length=1, max_length=800)
    failure_reasons: list[str] = Field(default_factory=list, max_length=5)


class ScenarioScores(HarnessModel):
    form_state_accuracy: float = Field(ge=0, le=1)
    context_retention: Optional[float] = Field(default=None, ge=0, le=1)
    unnecessary_repetition_rate: float = Field(ge=0, le=1)
    clarification_quality: Optional[float] = Field(default=None, ge=1, le=5)
    recovery_success: Optional[float] = Field(default=None, ge=0, le=1)
    heuristic_naturalness: float = Field(ge=1, le=5)
    invention_failures: int = Field(ge=0)
    latest_answer_adherence: Optional[float] = Field(default=None, ge=0, le=1)
    contradiction_failures: int = Field(default=0, ge=0)
    volunteered_fact_recall: Optional[float] = Field(default=None, ge=0, le=1)
    redundant_question_rate: Optional[float] = Field(default=None, ge=0, le=1)
    side_question_recovery: Optional[float] = Field(default=None, ge=0, le=1)
    unnecessary_push_rate: Optional[float] = Field(default=None, ge=0, le=1)
    speech_suitability: Optional[float] = Field(default=None, ge=0, le=1)
    acknowledgement_rate: Optional[float] = Field(default=None, ge=0, le=1)
    interruption_recovery: Optional[float] = Field(default=None, ge=0, le=1)
    clarification_success: Optional[float] = Field(default=None, ge=0, le=1)
    human_helper_behavior_rate: Optional[float] = Field(default=None, ge=0, le=1)
    confirmed_field_count: int = Field(default=0, ge=0)
    turns_per_confirmed_field: Optional[float] = Field(default=None, ge=0)
    confirmation_boundary_failures: int = Field(default=0, ge=0)


class ScenarioReport(HarnessModel):
    scenario_id: str
    title: str
    purpose: str
    persona: Persona
    fixture: str
    tags: list[str]
    expected_final_state: ExpectedFinalState
    actual_form_state: dict[str, dict[str, Any]]
    transcript: list[RecordedTurn]
    scores: ScenarioScores
    deterministic_failures: list[str]
    qualitative_assessment: Optional[QualitativeAssessment] = None
    qualitative_error: Optional[str] = None


class SuiteMetrics(HarnessModel):
    scenario_count: int
    turn_count: int
    completed_turn_rate: float
    form_state_accuracy: float
    context_retention_rate: Optional[float]
    unnecessary_repetition_rate: float
    clarification_quality: float
    recovery_success_rate: float
    heuristic_naturalness: float
    judged_naturalness: Optional[float]
    judged_context_awareness: Optional[float]
    judged_clarification_quality: Optional[float]
    judged_recovery_quality: Optional[float]
    invention_failures: int
    deterministic_failure_count: int
    qualitative_failure_count: int
    average_turn_latency_ms: float
    latest_answer_adherence_rate: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
    )
    contradiction_failure_count: int = Field(default=0, ge=0)
    volunteered_fact_recall_rate: Optional[float] = Field(default=None, ge=0, le=1)
    redundant_question_rate: Optional[float] = Field(default=None, ge=0, le=1)
    side_question_recovery_rate: Optional[float] = Field(default=None, ge=0, le=1)
    unnecessary_push_rate: Optional[float] = Field(default=None, ge=0, le=1)
    speech_suitability_rate: Optional[float] = Field(default=None, ge=0, le=1)
    acknowledgement_rate: Optional[float] = Field(default=None, ge=0, le=1)
    interruption_recovery_rate: Optional[float] = Field(default=None, ge=0, le=1)
    clarification_success_rate: Optional[float] = Field(default=None, ge=0, le=1)
    human_helper_behavior_rate: Optional[float] = Field(default=None, ge=0, le=1)
    behavior_check_coverage_rate: float = Field(default=0, ge=0, le=1)
    turns_per_confirmed_field: Optional[float] = Field(default=None, ge=0)
    confirmation_boundary_failure_count: int = Field(default=0, ge=0)
    judged_human_helper_resemblance: Optional[float] = None
    correctness_gate_passed: bool = False
    human_helper_gate_passed: bool = False


class SuiteReport(HarnessModel):
    report_schema_version: int = 2
    run_id: str
    label: str
    created_at: str
    git_revision: Optional[str]
    suite_id: str
    suite_digest: str
    target: str
    model: str
    judge_model: Optional[str]
    metrics: SuiteMetrics
    scenarios: list[ScenarioReport]
    correctness_gate_failures: list[str] = Field(default_factory=list)
    human_helper_gate_failures: list[str] = Field(default_factory=list)

    @classmethod
    def timestamp(cls) -> str:
        return datetime.now(timezone.utc).isoformat()


class MetricDelta(HarnessModel):
    baseline: float
    candidate: float
    delta: float
    direction: Literal["higher_is_better", "lower_is_better"]


class ComparisonReport(HarnessModel):
    baseline_run_id: str
    candidate_run_id: str
    comparable_suite: bool
    metric_deltas: dict[str, MetricDelta]
    fixed_failures: list[str]
    new_failures: list[str]
    unchanged_failures: list[str]


class PairwiseScenarioAssessment(HarnessModel):
    scenario_id: str
    preferred: Literal["baseline", "candidate", "tie"]
    attentiveness_winner: Literal["baseline", "candidate", "tie"]
    helpfulness_winner: Literal["baseline", "candidate", "tie"]
    conversational_flow_winner: Literal["baseline", "candidate", "tie"]
    user_effort_winner: Literal["baseline", "candidate", "tie"]
    safety_concern: bool
    reason: str = Field(min_length=1, max_length=800)


class PairwiseComparisonReport(HarnessModel):
    baseline_run_id: str
    candidate_run_id: str
    comparable_suite: bool
    judge_model: str
    candidate_wins: int = Field(ge=0)
    baseline_wins: int = Field(ge=0)
    ties: int = Field(ge=0)
    assessments: list[PairwiseScenarioAssessment]
