from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Mapping, Optional, Union

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, PyPdfError


PdfFieldValue = Union[str, bool]


class PdfExtractionError(ValueError):
    """Raised when an uploaded file cannot be read as a PDF."""


class PdfFillingError(ValueError):
    """Raised when field values cannot be applied to a PDF."""


@dataclass(frozen=True)
class PdfField:
    id: str
    type: str
    options: Optional[list[str]] = None


def extract_acroform_fields(pdf_data: bytes) -> list[PdfField]:
    fields = _read_pdf(pdf_data).get_fields() or {}

    extracted_fields = []
    for field_id, field in fields.items():
        if _is_structural_field(field):
            continue

        field_type = _field_type(field)
        extracted_fields.append(
            PdfField(
                id=field_id,
                type=field_type,
                options=_field_options(field, field_type),
            )
        )

    return sorted(extracted_fields, key=lambda field: field.id)


def fill_acroform_fields(
    pdf_data: bytes,
    values: Mapping[str, PdfFieldValue],
) -> bytes:
    reader = _read_pdf(pdf_data)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    fields = writer.get_fields() or {}
    missing_fields = sorted(set(values) - set(fields))
    if missing_fields:
        raise PdfFillingError(
            f"Unknown PDF field IDs: {', '.join(missing_fields)}"
        )

    normalized_values = {
        field_id: _normalize_fill_value(field_id, fields[field_id], value)
        for field_id, value in values.items()
    }

    try:
        writer.update_page_form_field_values(
            None,
            normalized_values,
            auto_regenerate=False,
        )
        output = BytesIO()
        writer.write(output)
    except PyPdfError as error:
        raise PdfFillingError("Could not fill the uploaded PDF") from error

    return output.getvalue()


def _read_pdf(pdf_data: bytes) -> PdfReader:
    if not pdf_data.startswith(b"%PDF-"):
        raise PdfExtractionError("Uploaded file is not a valid PDF")

    try:
        return PdfReader(BytesIO(pdf_data), strict=False)
    except PdfReadError as error:
        raise PdfExtractionError("Uploaded file is not a valid PDF") from error


def _field_type(field: dict[str, Any]) -> str:
    pdf_type = str(field.get("/FT", ""))
    flags = int(field.get("/Ff", 0))

    if pdf_type == "/Tx":
        return "textarea" if flags & (1 << 12) else "text"
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


def _normalize_fill_value(
    field_id: str,
    field: dict[str, Any],
    value: PdfFieldValue,
) -> str:
    field_type = _field_type(field)

    if field_type in {"text", "textarea"}:
        if not isinstance(value, str):
            raise PdfFillingError(f"Field '{field_id}' requires a string value")
        return value

    if field_type in {"dropdown", "list"}:
        if not isinstance(value, str):
            raise PdfFillingError(f"Field '{field_id}' requires a string value")

        options = _field_options(field, field_type) or []
        if value not in options:
            raise PdfFillingError(f"Invalid option for field '{field_id}': {value}")
        return value

    if field_type == "checkbox":
        if not isinstance(value, bool):
            raise PdfFillingError(f"Field '{field_id}' requires a boolean value")

        states = [str(state) for state in field.get("/_States_", [])]
        selected_states = [state for state in states if state != "/Off"]
        if value and not selected_states:
            raise PdfFillingError(f"Field '{field_id}' has no selectable state")
        return selected_states[0] if value else "/Off"

    raise PdfFillingError(
        f"Field '{field_id}' has unsupported type '{field_type}'"
    )


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


def _is_structural_field(field: dict[str, Any]) -> bool:
    return field.get("/FT") is None and bool(field.get("/Kids"))
