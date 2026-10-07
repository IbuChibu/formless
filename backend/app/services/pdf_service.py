from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
from typing import Any, Mapping, Optional, Union

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, PyPdfError
from pypdf.generic import NameObject, TextStringObject


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
    value: Optional[PdfFieldValue] = None


_SIMPLE_SUM_PATTERN = re.compile(
    r'^\s*AFSimple_Calculate\(\s*"SUM"\s*,\s*new\s+Array\s*\('
    r'(?P<field_names>(?:\s*"[^"]*"\s*,?)+)'
    r'\)\s*\)\s*;\s*$',
    re.DOTALL,
)
_NUMBER_PATTERN = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$"
)
_GROUPED_NUMBER_PATTERN = re.compile(
    r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d*)?$"
)


def extract_acroform_fields(pdf_data: bytes) -> list[PdfField]:
    fields = _read_pdf(pdf_data).get_fields() or {}

    extracted_fields = []
    for field_id, field in fields.items():
        if _is_structural_field(field) or _is_calculated_field(field):
            continue

        field_type = _field_type(field)
        extracted_fields.append(
            PdfField(
                id=field_id,
                type=field_type,
                options=_field_options(field, field_type),
                value=_field_value(field, field_type),
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

    calculated_fields = sorted(
        field_id
        for field_id in values
        if _is_calculated_field(fields[field_id])
    )
    if calculated_fields:
        raise PdfFillingError(
            "Calculated PDF fields cannot be set directly: "
            f"{', '.join(calculated_fields)}"
        )

    normalized_values = {
        field_id: _normalize_fill_value(field_id, fields[field_id], value)
        for field_id, value in values.items()
    }
    calculated_values = _calculate_standard_sums(fields, normalized_values)
    values_to_write = {**normalized_values, **calculated_values}
    appearance_values = {
        field_id: _appearance_value(field_id, fields[field_id], value)
        for field_id, value in values_to_write.items()
    }

    try:
        writer.update_page_form_field_values(
            None,
            appearance_values,
            auto_regenerate=False,
        )
        for field_id, value in values_to_write.items():
            if _field_type(fields[field_id]) == "number":
                _set_canonical_field_value(fields[field_id], value)

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
        if _has_standard_number_format(field):
            return "number"
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

    if field_type == "number":
        if not isinstance(value, str):
            raise PdfFillingError(f"Field '{field_id}' requires a numeric value")
        return _normalize_number_value(field_id, value)

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


def _field_value(
    field: dict[str, Any],
    field_type: str,
) -> Optional[PdfFieldValue]:
    value = field.get("/V")
    if value is None:
        value = field.get("/DV")
    if value is None:
        return None
    if field_type == "checkbox":
        return str(value) != "/Off"
    return str(value).removeprefix("/") if field_type == "radio" else str(value)


def _has_standard_number_format(field: dict[str, Any]) -> bool:
    javascript = _additional_action_javascript(field, "/F")
    return javascript is not None and javascript.strip().startswith(
        "AFNumber_Format("
    )


def _is_calculated_field(field: dict[str, Any]) -> bool:
    return _additional_action_javascript(field, "/C") is not None


def _additional_action_javascript(
    field: dict[str, Any],
    event: str,
) -> Optional[str]:
    additional_actions = field.get("/AA")
    if additional_actions is None:
        return None

    action_reference = additional_actions.get_object().get(event)
    if action_reference is None:
        return None

    action = action_reference.get_object()
    if str(action.get("/S")) != "/JavaScript":
        return None

    javascript = action.get("/JS")
    if javascript is None:
        return None

    javascript = javascript.get_object()
    if hasattr(javascript, "get_data"):
        return javascript.get_data().decode("utf-8", errors="replace")
    return str(javascript)


def _standard_sum_dependencies(field: dict[str, Any]) -> Optional[list[str]]:
    javascript = _additional_action_javascript(field, "/C")
    if javascript is None:
        return None

    match = _SIMPLE_SUM_PATTERN.fullmatch(javascript)
    if match is None:
        return None
    return re.findall(r'"([^"]*)"', match.group("field_names"))


def _calculate_standard_sums(
    fields: Mapping[str, dict[str, Any]],
    updated_values: Mapping[str, str],
) -> dict[str, str]:
    calculations = {
        field_id: dependencies
        for field_id, field in fields.items()
        if (dependencies := _standard_sum_dependencies(field)) is not None
    }
    resolved: dict[str, Decimal] = {}

    def resolve(field_id: str, active_fields: set[str]) -> Decimal:
        if field_id in resolved:
            return resolved[field_id]
        if field_id in active_fields:
            raise PdfFillingError("PDF calculation fields contain a cycle")

        dependencies = calculations.get(field_id)
        if dependencies is None:
            if field_id not in fields:
                raise PdfFillingError(
                    f"PDF calculation references unknown field '{field_id}'"
                )
            raw_value = updated_values.get(field_id)
            if raw_value is None:
                stored_value = fields[field_id].get("/V")
                raw_value = "" if stored_value is None else str(stored_value)
            return _number_as_decimal(field_id, raw_value, allow_blank=True)

        next_active_fields = {*active_fields, field_id}
        total = sum(
            (resolve(dependency, next_active_fields) for dependency in dependencies),
            Decimal(0),
        )
        resolved[field_id] = total
        return total

    for field_id in calculations:
        resolve(field_id, set())

    return {
        field_id: _decimal_to_pdf_value(value)
        for field_id, value in resolved.items()
    }


def _normalize_number_value(field_id: str, value: str) -> str:
    stripped_value = value.strip()
    if not stripped_value:
        return ""
    number = _number_as_decimal(field_id, stripped_value, allow_blank=False)
    return _decimal_to_pdf_value(number)


def _number_as_decimal(
    field_id: str,
    value: str,
    *,
    allow_blank: bool,
) -> Decimal:
    stripped_value = value.strip()
    if not stripped_value and allow_blank:
        return Decimal(0)
    if not (
        _NUMBER_PATTERN.fullmatch(stripped_value)
        or _GROUPED_NUMBER_PATTERN.fullmatch(stripped_value)
    ):
        raise PdfFillingError(f"Field '{field_id}' requires a numeric value")

    normalized_value = stripped_value.replace(",", "")

    try:
        number = Decimal(normalized_value)
    except InvalidOperation as error:
        raise PdfFillingError(
            f"Field '{field_id}' requires a numeric value"
        ) from error

    if not number.is_finite():
        raise PdfFillingError(f"Field '{field_id}' requires a numeric value")
    return number


def _decimal_to_pdf_value(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _appearance_value(
    field_id: str,
    field: dict[str, Any],
    value: str,
) -> str:
    if _field_type(field) != "number" or value == "":
        return value
    number = _number_as_decimal(field_id, value, allow_blank=False)
    return f"{number:,.2f}"


def _set_canonical_field_value(field: dict[str, Any], value: str) -> None:
    field_reference = getattr(field, "indirect_reference", None)
    target = field_reference.get_object() if field_reference else field
    target[NameObject("/V")] = TextStringObject(value)
