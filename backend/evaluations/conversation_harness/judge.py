from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import ValidationError

from .models import (
    PairwiseScenarioAssessment,
    QualitativeAssessment,
    ScenarioReport,
)


_JUDGE_SYSTEM_PROMPT = """You are evaluating a form-filling assistant conversation.
Score the assistant, not the synthetic user. Use only the supplied transcript,
persona, expected result, actual state, and deterministic findings.

Rubric:
- naturalness: warm, direct, flexible, human-sounding, and not robotic; penalize
  repeated status narration, bureaucratic templates, and unnecessarily long replies
- context_awareness: responds to the latest user utterance as authoritative for
  the current turn, remembers useful prior context, and never describes an older
  answer as though the user just said it
- clarification_quality: explains ambiguity specifically and helps the user answer
- recovery_quality: responds constructively to corrections or misunderstandings
- attentiveness: notices what the user actually said and acknowledges useful facts
- helpfulness: reduces confusion or effort instead of merely advancing the workflow
- conversational_flow: handles side questions and transitions without sounding scripted
- adaptability: changes approach when the user is confused, terse, nonlinear, or frustrated
- user_effort: 5 means low burden; 1 means repeated answers, confirmations, or prompting
- human_helper_resemblance: resembles a patient capable person completing the form
  alongside the user, rather than a form wizard or status machine
- treat a contradiction with the visible transcript or canonical field state as
  a serious failure even if the surrounding prose is fluent
- invents_information: true if the assistant supplies a personal fact or form value
  the user did not provide, or makes an unsupported factual claim

Use null for clarification_quality or recovery_quality when the conversation did
not exercise that behavior. Do not excuse wrong form state because prose sounded
good. Return only one JSON object with keys naturalness, context_awareness,
clarification_quality, recovery_quality, attentiveness, helpfulness,
conversational_flow, adaptability, user_effort, human_helper_resemblance,
invents_information, summary, and failure_reasons. Scores are integers from 1 to
5. Keep the summary under 120 words and include at most five concise failure reasons.
"""

_PAIRWISE_SYSTEM_PROMPT = """You are comparing two versions of a form-filling
assistant. The version labels are deliberately hidden. Judge which transcript more
closely resembles a patient, capable person sitting beside the user and helping them
complete the form. Correct form state, grounding, and explicit confirmation are hard
requirements. Prefer the assistant that answers the latest request, acknowledges
useful information, retains context, asks fewer redundant questions, handles side
questions and frustration well, and reduces user effort. Fluent prose cannot excuse
an incorrect effect or unsafe state.

Return one JSON object with keys preferred, attentiveness_winner,
helpfulness_winner, conversational_flow_winner, user_effort_winner,
safety_concern, and reason. Winner values must be A, B, or tie. Keep the reason under
120 words. Do not identify or guess which transcript is the baseline.
"""


class CompletionService(Protocol):
    @property
    def model(self) -> str: ...

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 600,
        json_response: bool = False,
    ) -> str: ...


class NemotronQualitativeJudge:
    def __init__(self, service: CompletionService) -> None:
        self._service = service

    @property
    def model(self) -> str:
        return self._service.model

    async def assess(self, report: ScenarioReport) -> QualitativeAssessment:
        payload: dict[str, Any] = {
            "scenario": {
                "id": report.scenario_id,
                "purpose": report.purpose,
                "tags": report.tags,
            },
            "persona": report.persona.model_dump(mode="json"),
            "expected_final_state": report.expected_final_state.model_dump(
                mode="json"
            ),
            "actual_form_state": report.actual_form_state,
            "deterministic_failures": report.deterministic_failures,
            "transcript": [
                {
                    "user": turn.visible_user_message,
                    "event": turn.user_event,
                    "assistant": turn.assistant_message,
                    "effect": turn.response_effect,
                    "state": turn.response_state,
                    "error": turn.error,
                }
                for turn in report.transcript
            ],
        }
        base_prompt = (
            "EVALUATION_DATA\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\nEND_EVALUATION_DATA"
        )
        validation_error: Exception | None = None
        for attempt in range(2):
            user_prompt = base_prompt
            if attempt:
                user_prompt += (
                    "\nYour previous response did not match the required rubric. "
                    "Return one valid JSON object. Use only integer scores 1-5, "
                    "or null for optional scores that were not exercised."
                )
            raw = await self._service.complete(
                system_prompt=_JUDGE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=700,
                json_response=True,
            )
            try:
                return QualitativeAssessment.model_validate_json(
                    _json_object(raw)
                )
            except (ValidationError, ValueError) as error:
                validation_error = error
        raise ValueError("Qualitative judge returned an invalid rubric") from (
            validation_error
        )


class NemotronPairwiseJudge:
    def __init__(self, service: CompletionService) -> None:
        self._service = service

    @property
    def model(self) -> str:
        return self._service.model

    async def assess(
        self,
        baseline: ScenarioReport,
        candidate: ScenarioReport,
        *,
        candidate_first: bool,
    ) -> PairwiseScenarioAssessment:
        ordered = (
            [("A", candidate), ("B", baseline)]
            if candidate_first
            else [("A", baseline), ("B", candidate)]
        )
        payload = {
            label: _pairwise_scenario_payload(report)
            for label, report in ordered
        }
        raw = await self._service.complete(
            system_prompt=_PAIRWISE_SYSTEM_PROMPT,
            user_prompt=(
                "BLINDED_COMPARISON_DATA\n"
                + json.dumps(payload, ensure_ascii=False)
                + "\nEND_BLINDED_COMPARISON_DATA"
            ),
            max_tokens=700,
            json_response=True,
        )
        parsed = json.loads(_json_object(raw))
        if not isinstance(parsed, dict):
            raise ValueError("Pairwise judge response must be an object")
        mapping = {
            "A": "candidate" if candidate_first else "baseline",
            "B": "baseline" if candidate_first else "candidate",
            "tie": "tie",
        }

        def winner(name: str) -> str:
            value = parsed.get(name)
            if not isinstance(value, str):
                raise ValueError(f"Pairwise judge omitted {name}")
            normalized = value.strip()
            if normalized.casefold() == "tie":
                normalized = "tie"
            else:
                normalized = normalized.upper()
            if normalized not in mapping:
                raise ValueError(f"Pairwise judge returned invalid {name}")
            return mapping[normalized]

        return PairwiseScenarioAssessment.model_validate(
            {
                "scenario_id": baseline.scenario_id,
                "preferred": winner("preferred"),
                "attentiveness_winner": winner("attentiveness_winner"),
                "helpfulness_winner": winner("helpfulness_winner"),
                "conversational_flow_winner": winner(
                    "conversational_flow_winner"
                ),
                "user_effort_winner": winner("user_effort_winner"),
                "safety_concern": parsed.get("safety_concern"),
                "reason": parsed.get("reason"),
            }
        )


def _pairwise_scenario_payload(report: ScenarioReport) -> dict[str, Any]:
    return {
        "purpose": report.purpose,
        "expected_final_state": report.expected_final_state.model_dump(mode="json"),
        "actual_form_state": report.actual_form_state,
        "deterministic_failures": report.deterministic_failures,
        "transcript": [
            {
                "user": turn.visible_user_message,
                "assistant": turn.assistant_message,
                "effect": turn.response_effect,
                "behavior_failures": turn.behavior_failures,
            }
            for turn in report.transcript
        ],
    }


def _json_object(raw: str) -> str:
    value = raw.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Judge response must be an object")
    return json.dumps(parsed)
