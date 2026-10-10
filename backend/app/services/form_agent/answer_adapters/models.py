from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from ..value_normalizer import FormFieldValue


@dataclass(frozen=True)
class MatchedAnswer:
    value: FormFieldValue
    kind: Literal["matched"] = "matched"


@dataclass(frozen=True)
class ClarificationNeeded:
    reason: str
    accepted_shape: str
    kind: Literal["clarification_needed"] = "clarification_needed"

    def __post_init__(self) -> None:
        if not self.reason.strip() or not self.accepted_shape.strip():
            raise ValueError(
                "Clarifications require a reason and accepted answer shape"
            )


@dataclass(frozen=True)
class NotApplicable:
    kind: Literal["not_applicable"] = "not_applicable"


AnswerAdapterResult = Union[
    MatchedAnswer,
    ClarificationNeeded,
    NotApplicable,
]
