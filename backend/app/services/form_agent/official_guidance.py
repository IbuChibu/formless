from __future__ import annotations

from pathlib import Path
import re
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import (
    ExplainAction,
    FocusFieldEvent,
    FormAgentAction,
    FormAgentError,
    FormAgentRequest,
    OfficialGuidanceCitation,
    ProposeAction,
    request_active_field_id,
    request_message,
)


MAX_SELECTED_GUIDANCE = 2
MAX_GUIDANCE_CONTEXT_CHARS = 1000
_GUIDANCE_DIRECTORY = Path(__file__).with_name("guidance")
_ALLOWED_SOURCE_HOSTS = frozenset(
    {
        "www.uscis.gov",
        "legacy.sba.gov",
    }
)
_QUESTION_PATTERN = re.compile(
    r"\b(?:why|what|which|who|when|where|how|explain|meaning|mean|"
    r"instructions?|required?|requirements?|rule|purpose|help)\b",
    re.IGNORECASE,
)
_PURPOSE_PATTERN = re.compile(
    r"(?:\bwhy\b|\bpurpose\b|\breason\b|\bused\s+for\b)",
    re.IGNORECASE,
)
_AUTHORITATIVE_PATTERN = re.compile(
    r"(?:\bwhy\b|\bpurpose\b|\breason\b|\bofficial\b|"
    r"\binstructions?\b|\brequired?\b|\brequirements?\b|\brule\b|"
    r"\bmust\b|\ballowed?\b|\beligib(?:le|ility)\b)",
    re.IGNORECASE,
)


class _GuidanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _GuidanceSource(_GuidanceModel):
    source_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=1000)
    retrieved_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def validate_allowlisted_url(self) -> _GuidanceSource:
        parsed_url = urlparse(self.url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname not in _ALLOWED_SOURCE_HOSTS
        ):
            raise ValueError("Official guidance source URL is not allowlisted")
        return self


class _GuidanceEntry(_GuidanceModel):
    entry_id: str = Field(min_length=1, max_length=100)
    topics: list[Literal["purpose", "field", "requirements"]] = Field(
        min_length=1,
        max_length=3,
    )
    applies_to_all: bool = False
    field_ids: list[str] = Field(default_factory=list, max_length=40)
    field_id_prefixes: list[str] = Field(default_factory=list, max_length=10)
    section_terms: list[str] = Field(default_factory=list, max_length=10)
    excerpt: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def validate_scope(self) -> _GuidanceEntry:
        if not (
            self.applies_to_all
            or self.field_ids
            or self.field_id_prefixes
            or self.section_terms
        ):
            raise ValueError("Guidance entries require an explicit scope")
        return self


class GuidanceResource(_GuidanceModel):
    form_id: str = Field(min_length=1, max_length=100)
    form_version: str = Field(min_length=1, max_length=100)
    source: _GuidanceSource
    entries: list[_GuidanceEntry] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_entries(self) -> GuidanceResource:
        entry_ids = [entry.entry_id for entry in self.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("Guidance entry IDs must be unique")
        return self


def load_guidance_resources(
    directory: Path = _GUIDANCE_DIRECTORY,
) -> tuple[GuidanceResource, ...]:
    resources = tuple(
        GuidanceResource.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    )
    keys = [(resource.form_id, resource.form_version) for resource in resources]
    if len(keys) != len(set(keys)):
        raise ValueError("Official guidance form/version keys must be unique")
    return resources


GUIDANCE_RESOURCES = load_guidance_resources()


def select_official_guidance(
    request: FormAgentRequest,
    resources: Optional[tuple[GuidanceResource, ...]] = None,
) -> tuple[OfficialGuidanceCitation, ...]:
    if not _is_guidance_request(request):
        return ()

    form_context = request.form_context
    if form_context.form_id is None or form_context.form_version is None:
        return ()
    resource = next(
        (
            candidate
            for candidate in (
                GUIDANCE_RESOURCES if resources is None else resources
            )
            if candidate.form_id == form_context.form_id
            and candidate.form_version == form_context.form_version
        ),
        None,
    )
    if resource is None:
        return ()

    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        return ()
    active_field = next(
        field for field in request.fields if field.id == active_field_id
    )
    message = request_message(request)
    wants_purpose = _PURPOSE_PATTERN.search(message) is not None
    ranked_entries: list[tuple[int, int, _GuidanceEntry]] = []
    for order, entry in enumerate(resource.entries):
        if wants_purpose:
            if "purpose" not in entry.topics:
                continue
        elif "purpose" in entry.topics and len(entry.topics) == 1:
            continue

        score = _entry_score(entry, active_field.id, active_field.section)
        if score == 0:
            continue
        if wants_purpose and "purpose" in entry.topics:
            score += 20
        if (
            "requirements" in entry.topics
            and _AUTHORITATIVE_PATTERN.search(message) is not None
        ):
            score += 3
        ranked_entries.append((score, -order, entry))

    citations = []
    used_characters = 0
    for _, _, entry in sorted(ranked_entries, reverse=True):
        if len(citations) >= MAX_SELECTED_GUIDANCE:
            break
        if used_characters + len(entry.excerpt) > MAX_GUIDANCE_CONTEXT_CHARS:
            continue
        citations.append(
            OfficialGuidanceCitation(
                source_id=resource.source.source_id,
                title=resource.source.title,
                organization=resource.source.organization,
                url=resource.source.url,
                form_version=resource.form_version,
                retrieved_at=resource.source.retrieved_at,
                excerpt=entry.excerpt,
                excerpt_kind="paraphrase",
            )
        )
        used_characters += len(entry.excerpt)
    return tuple(citations)


def authoritative_guidance_action(
    request: FormAgentRequest,
    guidance: tuple[OfficialGuidanceCitation, ...],
) -> Optional[ExplainAction]:
    message = request_message(request)
    if _AUTHORITATIVE_PATTERN.search(message) is None:
        return None
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        return None

    if guidance:
        return ExplainAction(
            action="explain",
            message=(
                "Plain-language explanation based on the official guidance "
                f"shown below: {guidance[0].excerpt}"
            ),
            field_id=active_field_id,
        )
    return ExplainAction(
        action="explain",
        message=(
            "No relevant approved official guidance is available for this "
            "form version and field. The available form context does not "
            "provide an authoritative reason or rule, so I cannot infer one. "
            "Check the form's official instructions or ask the issuing "
            "organisation."
        ),
        field_id=active_field_id,
    )


def validate_guidance_action(
    action: FormAgentAction,
    guidance: tuple[OfficialGuidanceCitation, ...],
) -> None:
    if guidance and isinstance(action, ProposeAction):
        raise FormAgentError(
            "Official guidance cannot supply a personal field value"
        )


def _is_guidance_request(request: FormAgentRequest) -> bool:
    if isinstance(request.event, FocusFieldEvent):
        return True
    message = request_message(request)
    return message.endswith("?") or _QUESTION_PATTERN.search(message) is not None


def _entry_score(
    entry: _GuidanceEntry,
    field_id: str,
    section: Optional[str],
) -> int:
    score = 1 if entry.applies_to_all else 0
    if field_id in entry.field_ids:
        score += 12
    if any(field_id.startswith(prefix) for prefix in entry.field_id_prefixes):
        score += 8
    if section is not None and any(
        term.casefold() in section.casefold() for term in entry.section_terms
    ):
        score += 6
    return score
