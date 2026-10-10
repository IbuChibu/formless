from __future__ import annotations

import re
from typing import Annotated, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    model_validator,
)

from .value_normalizer import SupportedFieldType, validate_field_value


BoundedAgentString = Annotated[
    StrictStr,
    Field(min_length=1, max_length=2000),
]
BoundedOption = Annotated[
    StrictStr,
    Field(min_length=1, max_length=500),
]
BoundedInstruction = Annotated[
    StrictStr,
    Field(min_length=1, max_length=500),
]
AgentFieldValue = Union[BoundedAgentString, StrictBool]
FieldStatus = Literal["unanswered", "confirmed", "skipped"]

MAX_AGENT_FIELDS = 250
MAX_HISTORY_MESSAGES = 8
MAX_FORM_INSTRUCTIONS = 8

_PLACEHOLDER_OPTION_PATTERN = re.compile(
    r"^(?:please\s+)?(?:select|choose)(?:\s+(?:one|an?\s+option))?$",
    re.IGNORECASE,
)


class FormAgentError(RuntimeError):
    """Raised when the Form Agent cannot return a safe validated action."""


class _AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FormAgentFormContext(_AgentModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    instructions: list[BoundedInstruction] = Field(
        default_factory=list,
        max_length=MAX_FORM_INSTRUCTIONS,
    )


class FormAgentField(_AgentModel):
    id: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=1000)
    question: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    help_text: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    section: Optional[str] = Field(default=None, min_length=1, max_length=500)
    page_context: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    type: SupportedFieldType
    page: Optional[int] = Field(default=None, ge=1)
    options: Optional[list[BoundedOption]] = Field(default=None, max_length=100)
    status: FieldStatus = "unanswered"
    confirmed_value: Optional[AgentFieldValue] = None

    @model_validator(mode="after")
    def validate_field_state(self) -> FormAgentField:
        if self.type == "dropdown":
            self.options = [
                option
                for option in (self.options or [])
                if not _is_placeholder_option(option)
            ]
            if not self.options:
                raise ValueError("Dropdown fields require at least one option")
            if (
                self.status == "confirmed"
                and isinstance(self.confirmed_value, str)
                and _is_placeholder_option(self.confirmed_value)
            ):
                self.status = "unanswered"
                self.confirmed_value = None

        if self.status == "confirmed":
            if self.confirmed_value is None:
                raise ValueError("Confirmed fields require a confirmed value")
            validate_field_value(
                self.type,
                self.options,
                self.confirmed_value,
            )
        elif self.confirmed_value is not None:
            raise ValueError(
                "Only confirmed fields may include a confirmed value"
            )

        return self


class FormAgentMessage(_AgentModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class FormAgentRequest(_AgentModel):
    form_context: FormAgentFormContext = Field(
        default_factory=FormAgentFormContext
    )
    fields: list[FormAgentField] = Field(
        min_length=1,
        max_length=MAX_AGENT_FIELDS,
    )
    active_field_id: Optional[str] = Field(default=None, max_length=500)
    message: str = Field(min_length=1, max_length=2000)
    history: list[FormAgentMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_MESSAGES,
    )

    @model_validator(mode="after")
    def validate_field_references(self) -> FormAgentRequest:
        field_ids = [field.id for field in self.fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("Field IDs must be unique")

        if (
            self.active_field_id is not None
            and self.active_field_id not in field_ids
        ):
            raise ValueError("Active field ID must reference a supplied field")

        return self


class ExplainAction(_AgentModel):
    action: Literal["explain"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class ClarifyAction(_AgentModel):
    action: Literal["clarify"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class ProposeAction(_AgentModel):
    action: Literal["propose"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)
    value: AgentFieldValue


class SkipAction(_AgentModel):
    action: Literal["skip"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class NextAction(_AgentModel):
    action: Literal["next"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: Optional[str] = Field(default=None, max_length=500)


FormAgentAction = Annotated[
    Union[
        ExplainAction,
        ClarifyAction,
        ProposeAction,
        SkipAction,
        NextAction,
    ],
    Field(discriminator="action"),
]


def field_question(field: FormAgentField) -> str:
    return field.question or field.label


def truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[:max_length - 1].rstrip()}…"


def _is_placeholder_option(option: str) -> bool:
    normalized_option = option.strip().strip("-–—_:.…").strip()
    if not normalized_option:
        return True
    return _PLACEHOLDER_OPTION_PATTERN.fullmatch(normalized_option) is not None
