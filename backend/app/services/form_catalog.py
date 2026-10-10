from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KnownFormIdentity:
    form_id: str
    form_version: str


@dataclass(frozen=True)
class _KnownFormDefinition:
    identity: KnownFormIdentity
    title_fragment: str
    field_count: int
    required_field_ids: frozenset[str]
    version_marker: Optional[str] = None


_KNOWN_FORMS = (
    _KnownFormDefinition(
        identity=KnownFormIdentity(
            form_id="uscis-i9",
            form_version="01/20/25",
        ),
        title_fragment="Employment Eligibility Verification",
        field_count=128,
        required_field_ids=frozenset(
            {
                "Last Name (Family Name)",
                "US Social Security Number",
                "CB_Alt",
                "CB_Alt_2",
            }
        ),
        version_marker="Form I-9 Edition 01/20/25",
    ),
    _KnownFormDefinition(
        identity=KnownFormIdentity(
            form_id="sba-startup-costs",
            form_version="2023-07-17",
        ),
        title_fragment="Startup costs — Joe’s Pizza Place",
        field_count=93,
        required_field_ids=frozenset(
            {
                "Monthly rent expense 1",
                "Monthly actual cost 1",
                "One-time budget cost 1",
                "One-time actual cost 10",
            }
        ),
    ),
)


def identify_known_form(
    title: Optional[str],
    field_ids: list[str],
    document_text: str = "",
) -> Optional[KnownFormIdentity]:
    if title is None:
        return None

    field_id_set = set(field_ids)
    for definition in _KNOWN_FORMS:
        if (
            definition.title_fragment in title
            and len(field_ids) == definition.field_count
            and definition.required_field_ids <= field_id_set
            and (
                definition.version_marker is None
                or definition.version_marker in document_text
            )
        ):
            return definition.identity
    return None
