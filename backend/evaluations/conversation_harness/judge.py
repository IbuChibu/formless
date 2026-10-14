from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import ValidationError

from .models import QualitativeAssessment, ScenarioReport


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
- treat a contradiction with the visible transcript or canonical field state as
  a serious failure even if the surrounding prose is fluent
- invents_information: true if the assistant supplies a personal fact or form value
  the user did not provide, or makes an unsupported factual claim

Use null for clarification_quality or recovery_quality when the conversation did
not exercise that behavior. Do not excuse wrong form state because prose sounded
good. Return only one JSON object with keys naturalness, context_awareness,
clarification_quality, recovery_quality, invents_information, summary, and
failure_reasons. Scores are integers from 1 to 5. Keep the summary under 120 words
and include at most five concise failure reasons.
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
                    "or null for the two optional scores."
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
