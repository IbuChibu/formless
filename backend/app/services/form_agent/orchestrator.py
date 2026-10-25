from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from app.services.nemotron_service import NemotronService, NemotronServiceError
from app.services.tavily_service import (
    TavilyConfigurationError,
    TavilyService,
    TavilyServiceError,
)

from .answer_preparation import (
    PROSE_POLISH_UNSAFE_ERROR,
    prepare_proposal_action,
    prose_polish_candidate,
    prose_polish_is_safe,
)
from .answer_adapters import (
    AnswerAdapterResult,
    interpret_answer,
    merge_volunteered_candidates,
)
from .conversation_policy import (
    conflicting_guidance_action,
    deterministic_action,
    explanation_repair_fallback,
    insufficient_guidance_action,
    invalid_value_clarification,
    model_failure_fallback,
    normalize_action_message,
    response_for_action,
    unexpected_navigation_clarification,
    validate_action_for_turn,
    validate_event_transition,
)
from .intent_policy import TurnIntent
from .models import (
    AssistancePreferencesUpdatedAction,
    ClarifyAction,
    CorrectionStartedAction,
    ExplainAction,
    FieldReopenedAction,
    FieldSelectedAction,
    FormAgentError,
    FormAgentField,
    FormAgentRequest,
    FormAgentResponse,
    MAX_REMEMBERED_CANDIDATES,
    ProposeAction,
    ReplacementProposeAction,
    request_active_field_id,
    request_message,
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
    unavailable_web_guidance,
    validate_web_guidance_action,
)
from .turn_interpreter import (
    action_from_interpretation,
    interpret_turn,
    should_interpret_turn,
    turn_intent_from_interpretation,
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
        turn_interpretation_enabled: bool = True,
    ) -> None:
        self._nemotron_service = nemotron_service
        self._tavily_service = tavily_service
        self._answer_interpreter = answer_interpreter
        self._turn_interpretation_enabled = turn_interpretation_enabled

    async def respond(self, request: FormAgentRequest) -> FormAgentResponse:
        validate_event_transition(request)

        if request.conversation_state.phase in {
            "awaiting_answer",
            "awaiting_clarification",
        }:
            message = request_message(request)
            if message:
                remembered = merge_volunteered_candidates(
                    request.conversation_state.remembered_candidates,
                    request.fields,
                    request_active_field_id(request),
                    message,
                    self._answer_interpreter,
                    max_candidates=MAX_REMEMBERED_CANDIDATES,
                )
                if remembered != request.conversation_state.remembered_candidates:
                    request = request.model_copy(
                        update={
                            "conversation_state": (
                                request.conversation_state.model_copy(
                                    update={
                                        "remembered_candidates": remembered,
                                    }
                                )
                            )
                        }
                    )

        active_field_id = request_active_field_id(request)
        active_field = next(
            (
                field
                for field in request.fields
                if field.id == active_field_id
            ),
            None,
        )
        requested_prose_candidate = (
            prose_polish_candidate(active_field, request_message(request))
            if active_field is not None
            else None
        )

        policy_action = deterministic_action(
            request,
            self._answer_interpreter,
        )
        turn_intent_override: Optional[TurnIntent] = None
        if self._turn_interpretation_enabled and should_interpret_turn(
            request,
            policy_action,
        ):
            try:
                interpreted_turn = await interpret_turn(
                    self._nemotron_service,
                    request,
                )
            except (FormAgentError, NemotronServiceError):
                if policy_action is not None and not isinstance(
                    policy_action,
                    (ProposeAction, ReplacementProposeAction),
                ):
                    return response_for_action(policy_action, request)
                fallback = model_failure_fallback(request)
                if fallback is not None:
                    return response_for_action(fallback, request)
            else:
                turn_intent_override = turn_intent_from_interpretation(
                    interpreted_turn,
                    request,
                )
                if turn_intent_override is None:
                    try:
                        interpreted_action, request = action_from_interpretation(
                            request,
                            interpreted_turn,
                            self._answer_interpreter,
                        )
                        if interpreted_action is not None:
                            if not isinstance(
                                interpreted_action,
                                (
                                    AssistancePreferencesUpdatedAction,
                                    CorrectionStartedAction,
                                    FieldReopenedAction,
                                    FieldSelectedAction,
                                ),
                            ):
                                validate_action_against_request(
                                    interpreted_action,
                                    request,
                                )
                    except FormAgentError:
                        interpreted_action = None
                    if interpreted_action is not None:
                        return response_for_action(
                            normalize_action_message(
                                interpreted_action,
                                request,
                            ),
                            request,
                        )

        if (
            turn_intent_override == "uncertain_answer"
            and isinstance(policy_action, ClarifyAction)
        ):
            return response_for_action(policy_action, request)

        if policy_action is not None and turn_intent_override is None:
            return response_for_action(policy_action, request)

        guidance = select_official_guidance(request)
        if guidance:
            guidance_action = authoritative_guidance_action(request, guidance)
            if guidance_action is not None:
                return response_for_action(
                    guidance_action,
                    request,
                    guidance,
                )

        web_guidance = None
        web_lookup = plan_web_guidance_lookup(request, guidance)
        if web_lookup is not None and self._tavily_service is not None:
            try:
                web_results = await self._tavily_service.search(
                    web_lookup.query
                )
            except TavilyConfigurationError:
                web_guidance = unavailable_web_guidance(
                    web_lookup,
                    "not_configured",
                )
            except TavilyServiceError:
                web_guidance = unavailable_web_guidance(
                    web_lookup,
                    "provider_failure",
                )
            else:
                web_guidance = prepare_web_guidance(
                    request,
                    web_lookup,
                    web_results,
                )

            if web_guidance.status in {"empty", "unavailable"}:
                return response_for_action(
                    insufficient_guidance_action(request, web_guidance),
                    request,
                    web_guidance=web_guidance,
                    preserve_conversation_phase=True,
                )
            if web_guidance.status == "conflicting":
                return response_for_action(
                    conflicting_guidance_action(request, web_guidance),
                    request,
                    web_guidance=web_guidance,
                    preserve_conversation_phase=True,
                )

        guidance_action = authoritative_guidance_action(request, guidance)
        if guidance_action is not None and web_guidance is None:
            return response_for_action(
                guidance_action,
                request,
                guidance,
            )

        user_prompt = build_user_prompt(
            request,
            guidance,
            web_guidance,
            turn_intent_override=turn_intent_override,
        )
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
                original_model_value = (
                    action.value if isinstance(action, ProposeAction) else None
                )
                action = canonicalize_proposal_value(action, request)
                if isinstance(action, ProposeAction):
                    action = prepare_proposal_action(
                        action.model_copy(
                            update={
                                "original_value": (
                                    requested_prose_candidate
                                    if requested_prose_candidate is not None
                                    else original_model_value
                                    if original_model_value is not None
                                    else action.value
                                ),
                                "transformation": None,
                            }
                        ),
                        request,
                    )
                    if requested_prose_candidate is not None:
                        prepared_value = action.value
                        if not isinstance(prepared_value, str) or not (
                            prose_polish_is_safe(
                                requested_prose_candidate,
                                prepared_value,
                            )
                        ):
                            raise FormAgentError(PROSE_POLISH_UNSAFE_ERROR)
                        action = action.model_copy(
                            update={
                                "original_value": requested_prose_candidate,
                                "transformation": (
                                    "Grammar and presentation suggested; "
                                    "review the wording before confirming."
                                    if prepared_value
                                    != requested_prose_candidate
                                    else None
                                ),
                            }
                        )
                    if (
                        request.conversation_state.phase
                        == "awaiting_replacement"
                        and active_field is not None
                        and active_field.status == "confirmed"
                        and active_field.confirmed_value is not None
                    ):
                        action = ReplacementProposeAction(
                            action="replacement_propose",
                            message=action.message,
                            field_id=action.field_id,
                            previous_confirmed_value=(
                                active_field.confirmed_value
                            ),
                            value=action.value,
                            original_value=(
                                action.original_value
                                if action.original_value is not None
                                else action.value
                            ),
                            transformation=action.transformation,
                        )
                validate_guidance_action(action, guidance)
                validate_web_guidance_action(action, web_guidance)
                validate_action_for_turn(
                    action,
                    request,
                    guidance,
                    turn_intent_override=turn_intent_override,
                )
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

            normalized_action = normalize_action_message(
                action,
                request,
                turn_intent_override,
            )
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
        if (
            requested_prose_candidate is not None
            and str(validation_error) == PROSE_POLISH_UNSAFE_ERROR
            and active_field is not None
        ):
            fallback_message = (
                "I couldn't safely change that wording without risking "
                "its meaning, so I kept your original text for review. "
                "It has not been applied to the form."
            )
            if (
                request.conversation_state.phase == "awaiting_replacement"
                and active_field.confirmed_value is not None
            ):
                fallback = ReplacementProposeAction(
                    action="replacement_propose",
                    message=fallback_message,
                    field_id=active_field.id,
                    previous_confirmed_value=active_field.confirmed_value,
                    value=requested_prose_candidate,
                    original_value=requested_prose_candidate,
                )
            else:
                fallback = ProposeAction(
                    action="propose",
                    message=fallback_message,
                    field_id=active_field.id,
                    value=requested_prose_candidate,
                    original_value=requested_prose_candidate,
                )
            validate_action_against_request(fallback, request)
            return response_for_action(fallback, request)
        repair_fallback = explanation_repair_fallback(
            validation_error,
            request,
            turn_intent_override,
        )
        if repair_fallback is not None:
            return response_for_action(repair_fallback, request)
        clarification = invalid_value_clarification(
            validation_error,
            request,
        )
        if clarification is not None:
            return response_for_action(clarification, request)
        fallback = model_failure_fallback(request, turn_intent_override)
        if fallback is not None:
            return response_for_action(fallback, request)
        raise validation_error
