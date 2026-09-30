from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfExtractionError(ValueError):
    """Raised when an uploaded file cannot be read as a PDF."""


@dataclass(frozen=True)
class PdfField:
    id: str
    type: str
    options: Optional[list[str]] = None


def extract_acroform_fields(pdf_data: bytes) -> list[PdfField]:
    if not pdf_data.startswith(b"%PDF-"):
        raise PdfExtractionError("Uploaded file is not a valid PDF")

    try:
        fields = PdfReader(BytesIO(pdf_data), strict=False).get_fields() or {}
    except PdfReadError as error:
        raise PdfExtractionError("Uploaded file is not a valid PDF") from error

    extracted_fields = []
    for field_id, field in fields.items():
        field_type = _field_type(field)
        extracted_fields.append(
            PdfField(
                id=field_id,
                type=field_type,
                options=_field_options(field, field_type),
            )
        )

    return sorted(extracted_fields, key=lambda field: field.id)


def _field_type(field: dict[str, Any]) -> str:
    pdf_type = str(field.get("/FT", ""))
    flags = int(field.get("/Ff", 0))

    if pdf_type == "/Tx":
        return "text"
    if pdf_type == "/Ch":
        return "dropdown" if flags & (1 << 17) else "list"
    if pdf_type == "/Btn":
        if flags & (1 << 16):
            return "button"
        if flags & (1 << 15):
            return "radio"
        return "checkbox"
    if pdf_type == "/Sig":
        return "signature"

    return "unknown"


def _field_options(field: dict[str, Any], field_type: str) -> Optional[list[str]]:
    raw_options = field.get("/Opt")
    if raw_options is None and field_type == "radio":
        raw_options = field.get("/_States_")
    if raw_options is None:
        return None

    options = []
    for raw_option in raw_options:
        if isinstance(raw_option, (list, tuple)) and len(raw_option) > 1:
            raw_option = raw_option[1]

        option = str(raw_option)
        if field_type == "radio" and option == "/Off":
            continue
        options.append(option.removeprefix("/") if field_type == "radio" else option)

    return options or None
