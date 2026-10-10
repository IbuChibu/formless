from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from app.services.nemotron_service import NemotronService
from app.services.tavily_service import TavilyService

from .answer_adapters import (
    AnswerAdapterResult,
    interpret_answer,
)
from .conversation_policy import (
    deterministic_action,
    invalid_value_clarification,
    normalize_action_message,
    response_for_action,
    unexpected_navigation_clarification,
    validate_event_transition,
)
from .models import (
    ExplainAction,
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    FormAgentResponse,
    request_active_field_id,
    truncate_text,
)
from .official_guidance import (
    authoritative_guidance_action,
    select_official_guidance,
    validate_guidance_action,
)
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
from .web_guidance import (
    plan_web_guidance_lookup,
    prepare_web_guidance,
    validate_web_guidance_action,
)


class FormAgentService:
    def __init__(
        self,
        nemotron_service: NemotronService,
        tavily_service: Optional[TavilyService] = None,
        *,
        answer_interpreter: Callable[
            [FormAgentField, str],
            AnswerAdapterResult,
        ] = interpret_answer,
    ) -> None:
        self._nemotron_service = nemotron_service
        self._tavily_service = tavily_service
        self._answer_interpreter = answer_interpreter

    async def respond(self, request: FormAgentRequest) -> FormAgentResponse:
        validate_event_transition(request)

        guidance = select_official_guidance(request)
        if guidance:
            guidance_action = authoritative_guidance_action(request, guidance)
            if guidance_action is not None:
                return response_for_action(
                    guidance_action,
                    request,
                    guidance,
                )

        policy_action = deterministic_action(
            request,
            self._answer_interpreter,
        )
        if policy_action is not None:
            return response_for_action(policy_action, request)

        web_guidance = None
        web_lookup = plan_web_guidance_lookup(request, guidance)
        if web_lookup is not None and self._tavily_service is not None:
            web_results = await self._tavily_service.search(web_lookup.query)
            web_guidance = prepare_web_guidance(
                request,
                web_lookup,
                web_results,
            )
            if web_guidance.status == "empty":
                active_field_id = request_active_field_id(request)
                if active_field_id is None:
                    raise FormAgentError(
                        "Web guidance requires an active field"
                    )
                return response_for_action(
                    ExplainAction(
                        action="explain",
                        message=(
                            "Tavily found no usable public web guidance for "
                            "this question. No form value was changed; you can "
                            "retry the search or continue manually."
                        ),
                        field_id=active_field_id,
                    ),
                    request,
                    web_guidance=web_guidance,
                )

        guidance_action = authoritative_guidance_action(request, guidance)
        if guidance_action is not None and web_guidance is None:
            return response_for_action(
                guidance_action,
                request,
                guidance,
            )

        user_prompt = build_user_prompt(request, guidance, web_guidance)
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
                validate_guidance_action(action, guidance)
                validate_web_guidance_action(action, web_guidance)
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

            normalized_action = normalize_action_message(action, request)
            if (
                isinstance(normalized_action, ExplainAction)
                and web_guidance is not None
                and web_guidance.status == "limited"
            ):
                normalized_action = normalized_action.model_copy(
                    update={
                        "message": truncate_text(
                            "The available live sources are limited or "
                            "conflicting, so this is not a definitive rule. "
                            + normalized_action.message,
                            4000,
                        )
                    }
                )
            return response_for_action(
                normalized_action,
                request,
                guidance if isinstance(normalized_action, ExplainAction) else (),
                (
                    web_guidance
                    if isinstance(normalized_action, ExplainAction)
                    else None
                ),
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
