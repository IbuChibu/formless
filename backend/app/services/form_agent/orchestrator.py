from __future__ import annotations

from typing import Optional

from app.services.nemotron_service import NemotronService

from .conversation_policy import (
    deterministic_action,
    invalid_value_clarification,
    normalize_action_message,
    unexpected_navigation_clarification,
    unsupported_purpose_action,
)
from .models import FormAgentAction, FormAgentError, FormAgentRequest
from .prompt_builder import (
    build_correction_user_prompt,
    build_user_prompt,
    system_prompt_for_attempt,
)
from .response_parser import (
    canonicalize_proposal_value,
    parse_action,
    validate_action_against_request,
)


class FormAgentService:
    def __init__(self, nemotron_service: NemotronService) -> None:
        self._nemotron_service = nemotron_service

    async def respond(self, request: FormAgentRequest) -> FormAgentAction:
        purpose_action = unsupported_purpose_action(request)
        if purpose_action is not None:
            return purpose_action

        policy_action = deterministic_action(request)
        if policy_action is not None:
            return policy_action

        user_prompt = build_user_prompt(request)
        validation_error: Optional[FormAgentError] = None
        attempt_user_prompt = user_prompt

        for attempt in range(2):
            raw_action = await self._nemotron_service.complete(
                system_prompt=system_prompt_for_attempt(attempt),
                user_prompt=attempt_user_prompt,
                max_tokens=600,
                json_response=True,
            )
            try:
                action = parse_action(raw_action)
                action = canonicalize_proposal_value(action, request)
                navigation_clarification = (
                    unexpected_navigation_clarification(action, request)
                )
                if navigation_clarification is not None:
                    return navigation_clarification
                validate_action_against_request(action, request)
            except FormAgentError as error:
                validation_error = error
                if attempt == 0:
                    attempt_user_prompt = build_correction_user_prompt(
                        user_prompt,
                        raw_action,
                        error,
                    )
                continue

            return normalize_action_message(action, request)

        if validation_error is None:
            raise FormAgentError("Form Agent returned an invalid action")
        clarification = invalid_value_clarification(
            validation_error,
            request,
        )
        if clarification is not None:
            return clarification
        raise validation_error
