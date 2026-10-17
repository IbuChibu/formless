from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StrictBool,
    StrictStr,
    model_serializer,
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
BoundedSupportNote = Annotated[
    StrictStr,
    Field(min_length=1, max_length=200),
]
AgentFieldValue = Union[BoundedAgentString, StrictBool]
FieldStatus = Literal["unanswered", "confirmed", "skipped"]
AssistanceNeed = Literal[
    "plain_language",
    "slower_pace",
    "organise_details",
    "reassurance",
    "explain_bureaucracy",
    "other",
]
InteractionModePreference = Literal["no_preference", "voice", "typing"]
ConversationPhase = Literal[
    "asking",
    "awaiting_answer",
    "awaiting_clarification",
    "awaiting_confirmation",
    "awaiting_replacement",
    "awaiting_replacement_confirmation",
    "field_confirmed",
    "field_skipped",
    "form_complete",
]

MAX_AGENT_FIELDS = 250
MAX_HISTORY_MESSAGES = 8
MAX_FORM_INSTRUCTIONS = 8
MAX_REMEMBERED_CANDIDATES = 5

_PLACEHOLDER_OPTION_PATTERN = re.compile(
    r"^(?:please\s+)?(?:select|choose)(?:\s+(?:one|an?\s+option))?$",
    re.IGNORECASE,
)


class FormAgentError(RuntimeError):
    """Raised when the Form Agent cannot return a safe validated action."""


class FormAgentTransitionError(FormAgentError):
    """Raised when a conversation event is invalid for the supplied state."""


class _AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AssistancePreferences(_AgentModel):
    support_needs: list[AssistanceNeed] = Field(
        default_factory=list,
        max_length=6,
    )
    interaction_mode: InteractionModePreference = "no_preference"
    other_note: Optional[BoundedSupportNote] = None
    assistance_language: Literal["en"] = "en"

    @model_validator(mode="after")
    def validate_support_choices(self) -> AssistancePreferences:
        if len(self.support_needs) != len(set(self.support_needs)):
            raise ValueError("Assistance support needs must be unique")
        has_other = "other" in self.support_needs
        if has_other != (self.other_note is not None):
            raise ValueError(
                "An other support need and its note must be supplied together"
            )
        return self


class FormAgentFormContext(_AgentModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    instructions: list[BoundedInstruction] = Field(
        default_factory=list,
        max_length=MAX_FORM_INSTRUCTIONS,
    )
    form_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    form_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_form_identity(self) -> FormAgentFormContext:
        if (self.form_id is None) != (self.form_version is None):
            raise ValueError(
                "Form ID and form version must be supplied together"
            )
        return self


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


class PendingProposal(_AgentModel):
    field_id: str = Field(min_length=1, max_length=500)
    value: AgentFieldValue


class PendingReplacementProposal(_AgentModel):
    operation: Literal["replacement"] = "replacement"
    field_id: str = Field(min_length=1, max_length=500)
    previous_confirmed_value: AgentFieldValue
    value: AgentFieldValue


class RememberedCandidate(_AgentModel):
    field_id: str = Field(min_length=1, max_length=500)
    original_value: AgentFieldValue
    value: AgentFieldValue


class ConversationState(_AgentModel):
    phase: ConversationPhase
    active_field_id: Optional[str] = Field(default=None, max_length=500)
    pending_proposal: Optional[
        Union[PendingReplacementProposal, PendingProposal]
    ] = None
    remembered_candidates: list[RememberedCandidate] = Field(
        default_factory=list,
        max_length=MAX_REMEMBERED_CANDIDATES,
    )

    @model_serializer(mode="wrap")
    def serialize_state(self, handler):
        data = handler(self)
        if not self.remembered_candidates:
            data.pop("remembered_candidates", None)
        return data

    @model_validator(mode="after")
    def validate_phase_shape(self) -> ConversationState:
        phases_requiring_active_field = {
            "awaiting_answer",
            "awaiting_clarification",
            "awaiting_confirmation",
            "awaiting_replacement",
            "awaiting_replacement_confirmation",
            "field_confirmed",
            "field_skipped",
        }
        if (
            self.phase in phases_requiring_active_field
            and self.active_field_id is None
        ):
            raise ValueError(
                f"{self.phase} requires an active field ID"
            )
        if self.phase in {"asking", "form_complete"}:
            if self.active_field_id is not None:
                raise ValueError(
                    f"{self.phase} cannot include an active field ID"
                )

        if self.phase in {
            "awaiting_confirmation",
            "awaiting_replacement_confirmation",
        }:
            if self.pending_proposal is None:
                raise ValueError(
                    f"{self.phase} requires a pending proposal"
                )
            if self.pending_proposal.field_id != self.active_field_id:
                raise ValueError(
                    "Pending proposal must match the active field ID"
                )
            is_replacement = isinstance(
                self.pending_proposal,
                PendingReplacementProposal,
            )
            if (
                self.phase == "awaiting_replacement_confirmation"
                and not is_replacement
            ) or (self.phase == "awaiting_confirmation" and is_replacement):
                raise ValueError(
                    "Pending proposal kind does not match the conversation phase"
                )
        elif self.pending_proposal is not None:
            raise ValueError(
                "Only a confirmation phase may include a pending proposal"
            )

        return self


class AdvanceEvent(_AgentModel):
    type: Literal["advance"]


class MessageEvent(_AgentModel):
    type: Literal["message"]
    content: BoundedAgentString


class FocusFieldEvent(_AgentModel):
    type: Literal["focus_field"]
    field_id: str = Field(min_length=1, max_length=500)
    content: BoundedAgentString


class ConfirmEvent(_AgentModel):
    type: Literal["confirm"]


class ConfirmEditEvent(_AgentModel):
    type: Literal["confirm_edit"]
    value: AgentFieldValue


class RejectEvent(_AgentModel):
    type: Literal["reject"]


class CancelCorrectionEvent(_AgentModel):
    type: Literal["cancel_correction"]


class SkipEvent(_AgentModel):
    type: Literal["skip"]
    field_id: str = Field(min_length=1, max_length=500)


FormAgentEvent = Annotated[
    Union[
        AdvanceEvent,
        MessageEvent,
        FocusFieldEvent,
        ConfirmEvent,
        ConfirmEditEvent,
        RejectEvent,
        CancelCorrectionEvent,
        SkipEvent,
    ],
    Field(discriminator="type"),
]


class FormAgentRequest(_AgentModel):
    form_context: FormAgentFormContext = Field(
        default_factory=FormAgentFormContext
    )
    fields: list[FormAgentField] = Field(
        min_length=1,
        max_length=MAX_AGENT_FIELDS,
    )
    conversation_state: ConversationState
    event: FormAgentEvent
    assistance_preferences: AssistancePreferences = Field(
        default_factory=AssistancePreferences
    )
    history: list[FormAgentMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_MESSAGES,
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_turn_contract(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "conversation_state" in data or "event" in data:
            return data
        if "message" not in data:
            return data

        migrated = dict(data)
        active_field_id = migrated.pop("active_field_id", None)
        message = migrated.pop("message")
        if active_field_id is None:
            migrated["conversation_state"] = {
                "phase": "asking",
                "active_field_id": None,
                "pending_proposal": None,
            }
            migrated["event"] = {"type": "advance"}
        else:
            migrated["conversation_state"] = {
                "phase": "awaiting_answer",
                "active_field_id": active_field_id,
                "pending_proposal": None,
            }
            migrated["event"] = {
                "type": "message",
                "content": message,
            }
        return migrated

    @model_validator(mode="after")
    def validate_field_references(self) -> FormAgentRequest:
        field_ids = [field.id for field in self.fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("Field IDs must be unique")

        active_field_id = self.conversation_state.active_field_id
        if active_field_id is not None and active_field_id not in field_ids:
            raise ValueError("Active field ID must reference a supplied field")
        pending_proposal = self.conversation_state.pending_proposal
        if (
            pending_proposal is not None
            and pending_proposal.field_id not in field_ids
        ):
            raise ValueError(
                "Pending proposal field ID must reference a supplied field"
            )
        remembered_field_ids = [
            candidate.field_id
            for candidate in self.conversation_state.remembered_candidates
        ]
        if len(remembered_field_ids) != len(set(remembered_field_ids)):
            raise ValueError("Remembered candidate field IDs must be unique")
        fields_by_id = {field.id: field for field in self.fields}
        for candidate in self.conversation_state.remembered_candidates:
            field = fields_by_id.get(candidate.field_id)
            if field is None:
                raise ValueError(
                    "Remembered candidate field ID must reference a supplied field"
                )
            if field.status != "unanswered":
                raise ValueError(
                    "Remembered candidates must reference unanswered fields"
                )
            try:
                validate_field_value(
                    field.type,
                    field.options,
                    candidate.value,
                )
            except ValueError as error:
                raise ValueError(
                    "Remembered candidate must be valid for its field"
                ) from error
        if (
            isinstance(self.event, FocusFieldEvent)
            and self.event.field_id not in field_ids
        ):
            raise ValueError("Focused field ID must reference a supplied field")

        return self


class ExplainAction(_AgentModel):
    action: Literal["explain"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class ClarifyAction(_AgentModel):
    action: Literal["clarify"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class ConversationAction(_AgentModel):
    action: Literal["conversation"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: Optional[str] = Field(default=None, max_length=500)


class ProposeAction(_AgentModel):
    action: Literal["propose"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)
    value: AgentFieldValue
    original_value: Optional[AgentFieldValue] = None
    transformation: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
    )


class ReplacementProposeAction(_AgentModel):
    action: Literal["replacement_propose"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)
    previous_confirmed_value: AgentFieldValue
    value: AgentFieldValue
    original_value: AgentFieldValue
    transformation: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
    )


class SkipAction(_AgentModel):
    action: Literal["skip"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class NextAction(_AgentModel):
    action: Literal["next"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: Optional[str] = Field(default=None, max_length=500)


class ConfirmedAction(_AgentModel):
    action: Literal["confirmed"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)
    value: AgentFieldValue


class RejectedAction(_AgentModel):
    action: Literal["rejected"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class ReplacementRejectedAction(_AgentModel):
    action: Literal["replacement_rejected"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class FieldSelectedAction(_AgentModel):
    action: Literal["field_selected"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class FieldReopenedAction(_AgentModel):
    action: Literal["field_reopened"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class CorrectionStartedAction(_AgentModel):
    action: Literal["correction_started"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class CorrectionCancelledAction(_AgentModel):
    action: Literal["correction_cancelled"]
    message: str = Field(min_length=1, max_length=4000)
    field_id: str = Field(min_length=1, max_length=500)


class OfficialGuidanceCitation(_AgentModel):
    source_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(min_length=1, max_length=300)
    url: str = Field(
        min_length=1,
        max_length=1000,
        pattern=r"^https://",
    )
    form_version: str = Field(min_length=1, max_length=100)
    retrieved_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    excerpt: str = Field(min_length=1, max_length=600)
    excerpt_kind: Literal["paraphrase"] = "paraphrase"


class WebGuidanceCitation(_AgentModel):
    source_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(
        min_length=1,
        max_length=1000,
        pattern=r"^https://",
    )
    hostname: str = Field(min_length=1, max_length=253)
    retrieved_at: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    )
    form_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    snippet: str = Field(min_length=1, max_length=500)
    source_quality: Literal[
        "issuing_organization",
        "public_authority",
        "general_web",
    ]


class WebGuidanceMetadata(_AgentModel):
    provider: Literal["tavily"] = "tavily"
    status: Literal[
        "used",
        "limited",
        "conflicting",
        "empty",
        "unavailable",
    ]
    topic: Literal["meaning", "purpose", "requirements", "where_to_find"]
    notice: str = Field(min_length=1, max_length=600)
    sources: list[WebGuidanceCitation] = Field(
        default_factory=list,
        max_length=3,
    )

    @model_validator(mode="after")
    def validate_status_sources(self) -> WebGuidanceMetadata:
        if self.status in {"empty", "unavailable"} and self.sources:
            raise ValueError(
                "Empty or unavailable web guidance cannot include sources"
            )
        if (
            self.status in {"used", "limited", "conflicting"}
            and not self.sources
        ):
            raise ValueError("Used web guidance requires sources")
        return self


FormAgentAction = Annotated[
    Union[
        ExplainAction,
        ClarifyAction,
        ConversationAction,
        ProposeAction,
        ReplacementProposeAction,
        SkipAction,
        NextAction,
        ConfirmedAction,
        RejectedAction,
        ReplacementRejectedAction,
        FieldSelectedAction,
        FieldReopenedAction,
        CorrectionStartedAction,
        CorrectionCancelledAction,
    ],
    Field(discriminator="action"),
]

ModelAction = Annotated[
    Union[
        ExplainAction,
        ClarifyAction,
        ConversationAction,
        ProposeAction,
        SkipAction,
        NextAction,
    ],
    Field(discriminator="action"),
]


class NoFormEffect(_AgentModel):
    effect: Literal["none"] = "none"
    field_id: Optional[str] = Field(default=None, max_length=500)


class ProposalEffect(_AgentModel):
    effect: Literal["proposal"] = "proposal"
    field_id: str = Field(min_length=1, max_length=500)
    original_value: AgentFieldValue
    prepared_value: AgentFieldValue
    transformation: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
    )


class ReplacementProposalEffect(_AgentModel):
    effect: Literal["replacement_proposal"] = "replacement_proposal"
    field_id: str = Field(min_length=1, max_length=500)
    previous_confirmed_value: AgentFieldValue
    original_value: AgentFieldValue
    prepared_value: AgentFieldValue
    transformation: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
    )


class ConfirmedEffect(_AgentModel):
    effect: Literal["confirmed"] = "confirmed"
    field_id: str = Field(min_length=1, max_length=500)
    value: AgentFieldValue


class RejectedEffect(_AgentModel):
    effect: Literal["rejected"] = "rejected"
    field_id: str = Field(min_length=1, max_length=500)


class SkippedEffect(_AgentModel):
    effect: Literal["skipped"] = "skipped"
    field_id: str = Field(min_length=1, max_length=500)


class FieldSelectedEffect(_AgentModel):
    effect: Literal["field_selected"] = "field_selected"
    field_id: str = Field(min_length=1, max_length=500)


class FieldReopenedEffect(_AgentModel):
    effect: Literal["field_reopened"] = "field_reopened"
    field_id: str = Field(min_length=1, max_length=500)


class CorrectionStartedEffect(_AgentModel):
    effect: Literal["correction_started"] = "correction_started"
    field_id: str = Field(min_length=1, max_length=500)


class ReplacementRejectedEffect(_AgentModel):
    effect: Literal["replacement_rejected"] = "replacement_rejected"
    field_id: str = Field(min_length=1, max_length=500)


class CorrectionCancelledEffect(_AgentModel):
    effect: Literal["correction_cancelled"] = "correction_cancelled"
    field_id: str = Field(min_length=1, max_length=500)


class CompletedEffect(_AgentModel):
    effect: Literal["completed"] = "completed"


FormAgentEffect = Annotated[
    Union[
        NoFormEffect,
        ProposalEffect,
        ReplacementProposalEffect,
        ConfirmedEffect,
        RejectedEffect,
        SkippedEffect,
        FieldSelectedEffect,
        FieldReopenedEffect,
        CorrectionStartedEffect,
        ReplacementRejectedEffect,
        CorrectionCancelledEffect,
        CompletedEffect,
    ],
    Field(discriminator="effect"),
]


class FormAgentResponse(_AgentModel):
    assistant_message: str = Field(min_length=1, max_length=4000)
    effect: FormAgentEffect
    conversation_state: ConversationState
    guidance: list[OfficialGuidanceCitation] = Field(
        default_factory=list,
        max_length=2,
    )
    web_guidance: Optional[WebGuidanceMetadata] = None

    _action: Optional[FormAgentAction] = PrivateAttr(default=None)

    @property
    def action(self) -> FormAgentAction:
        """Internal compatibility view; it is not part of the API payload."""
        if self._action is None:
            raise FormAgentError("Form Agent response has no internal action")
        return self._action

    def bind_internal_action(
        self,
        action: FormAgentAction,
    ) -> FormAgentResponse:
        self._action = action
        return self


def request_active_field_id(request: FormAgentRequest) -> Optional[str]:
    if isinstance(request.event, FocusFieldEvent):
        return request.event.field_id
    return request.conversation_state.active_field_id


def request_message(request: FormAgentRequest) -> str:
    if isinstance(request.event, (MessageEvent, FocusFieldEvent)):
        return request.event.content
    return ""


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
