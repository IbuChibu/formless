from __future__ import annotations

from typing import Optional

from app.services.nemotron_service import NemotronService

from .conversation_policy import (
    deterministic_action,
    invalid_value_clarification,
    normalize_action_message,
    response_for_action,
    unexpected_navigation_clarification,
    unsupported_purpose_action,
    validate_event_transition,
)
from .models import FormAgentError, FormAgentRequest, FormAgentResponse
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

    async def respond(self, request: FormAgentRequest) -> FormAgentResponse:
        validate_event_transition(request)

        purpose_action = unsupported_purpose_action(request)
        if purpose_action is not None:
            return response_for_action(purpose_action, request)

        policy_action = deterministic_action(request)
        if policy_action is not None:
            return response_for_action(policy_action, request)

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
                    return response_for_action(
                        navigation_clarification,
                        request,
                    )
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

            return response_for_action(
                normalize_action_message(action, request),
                request,
            )

        if validation_error is None:
            raise FormAgentError("Form Agent returned an invalid action")
        clarification = invalid_value_clarification(
            validation_error,
            request,
        )
        if clarification is not None:
            return response_for_action(clarification, request)
        raise validation_error
