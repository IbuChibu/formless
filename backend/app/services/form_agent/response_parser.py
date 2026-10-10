from __future__ import annotations

import json
import math

from pydantic import TypeAdapter, ValidationError

from .models import (
    FormAgentAction,
    FormAgentError,
    FormAgentRequest,
    NextAction,
    ProposeAction,
    SkipAction,
)
from .value_normalizer import canonicalize_field_value, validate_field_value


_ACTION_ADAPTER = TypeAdapter(FormAgentAction)


def parse_action(raw_action: str) -> FormAgentAction:
    try:
        action_data = json.loads(raw_action)
        if (
            isinstance(action_data, dict)
            and action_data.get("action") == "propose"
            and isinstance(action_data.get("value"), (int, float))
            and not isinstance(action_data.get("value"), bool)
        ):
            numeric_value = action_data["value"]
            if not math.isfinite(numeric_value):
                raise ValueError("Proposal numbers must be finite")
            action_data["value"] = _format_numeric_model_value(numeric_value)
        return _ACTION_ADAPTER.validate_python(action_data)
    except (json.JSONDecodeError, ValidationError, TypeError) as error:
        raise FormAgentError(
            "Form Agent returned an invalid action"
        ) from error


def canonicalize_proposal_value(
    action: FormAgentAction,
    request: FormAgentRequest,
) -> FormAgentAction:
    if not isinstance(action, ProposeAction):
        return action

    field = next(
        (field for field in request.fields if field.id == action.field_id),
        None,
    )
    if field is None:
        return action

    normalized_value = canonicalize_field_value(
        field.type,
        field.options,
        action.value,
    )
    return action.model_copy(update={"value": normalized_value})


def validate_action_against_request(
    action: FormAgentAction,
    request: FormAgentRequest,
) -> None:
    fields_by_id = {field.id: field for field in request.fields}
    unanswered_fields = [
        field for field in request.fields if field.status == "unanswered"
    ]

    if action.field_id is None:
        if not isinstance(action, NextAction) or unanswered_fields:
            raise FormAgentError("Form Agent returned an invalid action")
        return

    if (
        request.active_field_id is None
        and unanswered_fields
        and not isinstance(action, NextAction)
    ):
        raise FormAgentError(
            "Form Agent returned an action without an active field"
        )

    field = fields_by_id.get(action.field_id)
    if field is None:
        raise FormAgentError("Form Agent returned an unknown field ID")

    if (
        request.active_field_id is not None
        and not isinstance(action, NextAction)
        and action.field_id != request.active_field_id
    ):
        raise FormAgentError(
            "Form Agent returned an action for the wrong active field"
        )

    if isinstance(action, NextAction) and field.status != "unanswered":
        raise FormAgentError(
            "Form Agent returned a resolved field as the next field"
        )

    if (
        isinstance(action, NextAction)
        and unanswered_fields
        and action.field_id != unanswered_fields[0].id
    ):
        raise FormAgentError(
            "Form Agent did not return the first unanswered field"
        )

    if isinstance(action, SkipAction) and field.status != "unanswered":
        raise FormAgentError(
            "Form Agent returned a resolved field to skip"
        )

    if isinstance(action, ProposeAction):
        try:
            validate_field_value(field.type, field.options, action.value)
        except ValueError as error:
            raise FormAgentError(
                "Form Agent returned an invalid proposal value"
            ) from error


def _format_numeric_model_value(value: int | float) -> str:
    if isinstance(value, int) or value.is_integer():
        return str(int(value))
    return format(value, "f").rstrip("0").rstrip(".")
