from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr


FieldValue = Union[
    Annotated[StrictStr, Field(min_length=1, max_length=2000)],
    StrictBool,
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoEffect(_Model):
    type: Literal["none"]
    awaiting: Literal["answer", "clarification"] = "answer"


class ProposeValueEffect(_Model):
    type: Literal["propose_value"]
    field_id: str = Field(min_length=1, max_length=500)
    value: FieldValue
    heard_value: Optional[FieldValue] = None


class ConfirmProposalEffect(_Model):
    type: Literal["confirm_proposal"]


class RejectProposalEffect(_Model):
    type: Literal["reject_proposal"]


class SkipFieldEffect(_Model):
    type: Literal["skip_field"]
    field_id: str = Field(min_length=1, max_length=500)


class SelectFieldEffect(_Model):
    type: Literal["select_field"]
    field_id: str = Field(min_length=1, max_length=500)


class ChangeInputModeEffect(_Model):
    type: Literal["change_input_mode"]
    mode: Literal["voice", "typing", "no_preference"]


class UpdateAssistanceEffect(_Model):
    type: Literal["update_assistance"]
    support_needs: list[
        Literal[
            "plain_language",
            "slower_pace",
            "organise_details",
            "reassurance",
            "explain_bureaucracy",
        ]
    ] = Field(max_length=5)


class RequestGuidanceEffect(_Model):
    type: Literal["request_guidance"]
    field_id: str = Field(min_length=1, max_length=500)


ConversationV2Effect = Annotated[
    Union[
        NoEffect,
        ProposeValueEffect,
        ConfirmProposalEffect,
        RejectProposalEffect,
        SkipFieldEffect,
        SelectFieldEffect,
        ChangeInputModeEffect,
        UpdateAssistanceEffect,
        RequestGuidanceEffect,
    ],
    Field(discriminator="type"),
]


class ConversationV2Decision(_Model):
    reply: str = Field(min_length=1, max_length=4000)
    effect: ConversationV2Effect
