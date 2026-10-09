from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
from typing import Any, Mapping, Optional, Union

import pymupdf
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
    label: str
    type: str
    question: str
    page: Optional[int] = None
    options: Optional[list[str]] = None
    value: Optional[PdfFieldValue] = None
    help_text: Optional[str] = None
    section: Optional[str] = None
    page_context: Optional[str] = None


@dataclass(frozen=True)
class PdfFormContext:
    title: Optional[str] = None
    instructions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfExtraction:
    fields: list[PdfField]
    form_context: PdfFormContext


@dataclass(frozen=True)
class _WidgetLocation:
    page: int
    order: int


@dataclass(frozen=True)
class _WidgetPosition:
    field_id: str
    top: float
    left: float
    annotation_order: int


@dataclass(frozen=True)
class _Rectangle:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return max(0.0, self.right - self.left)

    @property
    def height(self) -> float:
        return max(0.0, self.bottom - self.top)


@dataclass(frozen=True)
class _NativeTextLine:
    text: str
    rectangle: _Rectangle
    block: int
    line: int
    font_size: float
    is_bold: bool


@dataclass(frozen=True)
class _NativeTextGroup:
    text: str
    rectangle: _Rectangle
    block: int
    first_line: int
    font_size: float
    is_bold: bool


@dataclass(frozen=True)
class _NativeFieldContext:
    question: Optional[str] = None
    help_text: Optional[str] = None
    section: Optional[str] = None
    page_context: Optional[str] = None


@dataclass(frozen=True)
class _NativePdfContext:
    fields: dict[str, _NativeFieldContext]
    form_context: PdfFormContext


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
_PLACEHOLDER_FIELD_LABELS = {"-", "n/a", "na", "none", "null", "undefined"}
_VISUAL_ROW_TOLERANCE = 8
_QUESTION_VERTICAL_GAP = 20
_HELP_VERTICAL_GAP = 48
_WRAPPED_LINE_GAP = 5
_MAX_CONTEXT_TEXT_LENGTH = 500
_HEADING_PATTERN = re.compile(
    r"^(?:section|part)\s+[a-z0-9]+\b|^[A-Z]\.[ \t]+",
    re.IGNORECASE,
)
_HELP_TEXT_PATTERN = re.compile(
    r"^(?:for\b|if\b|enter\b|use\b|see\b|note\b|please\b|when\b|"
    r"do not\b|only\b|this\b)",
    re.IGNORECASE,
)
_INSTRUCTION_TEXT_PATTERN = re.compile(
    r"\b(?:must|should|complete|choose|enter|use|do not|ensure|provide|"
    r"instructions?|this (?:form|worksheet)|fictional|not connected)\b",
    re.IGNORECASE,
)
_MAX_FORM_INSTRUCTIONS = 8


def extract_acroform_fields(pdf_data: bytes) -> list[PdfField]:
    return extract_acroform(pdf_data).fields


def extract_acroform(pdf_data: bytes) -> PdfExtraction:
    reader = _read_pdf(pdf_data)
    fields = reader.get_fields() or {}
    widget_locations = _field_widget_locations(reader)
    native_context = _extract_native_pdf_context(pdf_data)
    fallback_order = max(
        (location.order for location in widget_locations.values()),
        default=-1,
    ) + 1

    extracted_fields = []
    for source_order, (field_id, field) in enumerate(fields.items()):
        if _is_structural_field(field) or _is_calculated_field(field):
            continue

        field_type = _field_type(field)
        location = widget_locations.get(field_id)
        label = _field_label(field_id, field)
        context = native_context.fields.get(field_id, _NativeFieldContext())
        extracted_fields.append(
            (
                location.order if location is not None else fallback_order + source_order,
                PdfField(
                    id=field_id,
                    label=label,
                    type=field_type,
                    question=context.question or label,
                    page=location.page if location is not None else None,
                    options=_field_options(field, field_type),
                    value=_field_value(field, field_type),
                    help_text=context.help_text,
                    section=context.section,
                    page_context=context.page_context,
                ),
            )
        )

    return PdfExtraction(
        fields=[
            field
            for _, field in sorted(extracted_fields, key=lambda item: item[0])
        ],
        form_context=native_context.form_context,
    )


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


def _field_label(field_id: str, field: dict[str, Any]) -> str:
    alternate_name = field.get("/TU")
    if alternate_name is not None:
        label = " ".join(str(alternate_name).split())
        if label and label.casefold() not in _PLACEHOLDER_FIELD_LABELS:
            return label

    humanized_id = " ".join(re.sub(r"[._-]+", " ", field_id).split())
    return humanized_id[:1].upper() + humanized_id[1:]


def _extract_native_pdf_context(
    pdf_data: bytes,
) -> _NativePdfContext:
    try:
        document = pymupdf.open(stream=pdf_data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
        raise PdfExtractionError("Uploaded file is not a valid PDF") from error

    field_contexts: dict[str, _NativeFieldContext] = {}
    form_title: Optional[str] = None
    form_instructions: list[str] = []
    try:
        for page in document:
            widgets = list(page.widgets() or [])
            widget_rectangles = [
                _pymupdf_rectangle(widget.rect) for widget in widgets
            ]
            lines = _native_text_lines(page, widget_rectangles)
            groups = _native_text_groups(lines)
            page_title = _page_title(groups, page.rect.height)
            if form_title is None and page_title is not None:
                form_title = page_title
            for instruction in _page_instructions(
                groups,
                page_title,
                widget_rectangles,
                page.rect.height,
            ):
                if (
                    instruction not in form_instructions
                    and len(form_instructions) < _MAX_FORM_INSTRUCTIONS
                ):
                    form_instructions.append(instruction)

            for widget in widgets:
                field_id = widget.field_name
                if not field_id or field_id in field_contexts:
                    continue

                rectangle = _pymupdf_rectangle(widget.rect)
                question_group = _question_group(rectangle, groups)
                question = (
                    _clean_context_text(question_group.text)
                    if question_group is not None
                    else None
                )
                section = _field_section(rectangle, groups)
                field_contexts[field_id] = _NativeFieldContext(
                    question=question,
                    help_text=_field_help_text(
                        rectangle,
                        groups,
                        question_group,
                    ),
                    section=section,
                    page_context=_field_page_context(page_title, section),
                )
    finally:
        document.close()

    return _NativePdfContext(
        fields=field_contexts,
        form_context=PdfFormContext(
            title=form_title,
            instructions=tuple(form_instructions),
        ),
    )


def _native_text_lines(
    page: pymupdf.Page,
    widget_rectangles: list[_Rectangle],
) -> list[_NativeTextLine]:
    lines: list[_NativeTextLine] = []
    text_dictionary = page.get_text("dict", sort=True)

    for block_number, block in enumerate(text_dictionary.get("blocks", [])):
        if block.get("type") != 0:
            continue

        for line_number, line in enumerate(block.get("lines", [])):
            safe_spans = []
            for span in line.get("spans", []):
                text = " ".join(str(span.get("text", "")).split())
                rectangle = _coordinates_rectangle(span.get("bbox"))
                if not text or rectangle is None:
                    continue
                if any(
                    _rectangles_intersect(rectangle, widget_rectangle)
                    for widget_rectangle in widget_rectangles
                ):
                    continue
                safe_spans.append((text, rectangle, span))

            if not safe_spans:
                continue

            rectangle = _bounding_rectangle(
                [span_rectangle for _, span_rectangle, _ in safe_spans]
            )
            lines.append(
                _NativeTextLine(
                    text=" ".join(text for text, _, _ in safe_spans),
                    rectangle=rectangle,
                    block=block_number,
                    line=line_number,
                    font_size=max(
                        float(span.get("size", 0))
                        for _, _, span in safe_spans
                    ),
                    is_bold=any(
                        "bold" in str(span.get("font", "")).casefold()
                        or "demi" in str(span.get("font", "")).casefold()
                        for _, _, span in safe_spans
                    ),
                )
            )

    return lines


def _native_text_groups(
    lines: list[_NativeTextLine],
) -> list[_NativeTextGroup]:
    groups: list[_NativeTextGroup] = []

    for line in sorted(
        lines,
        key=lambda item: (
            item.block,
            item.rectangle.top,
            item.rectangle.left,
            item.line,
        ),
    ):
        previous = groups[-1] if groups else None
        if previous is not None and _is_wrapped_line(previous, line):
            groups[-1] = _NativeTextGroup(
                text=f"{previous.text} {line.text}",
                rectangle=_bounding_rectangle(
                    [previous.rectangle, line.rectangle]
                ),
                block=previous.block,
                first_line=previous.first_line,
                font_size=max(previous.font_size, line.font_size),
                is_bold=previous.is_bold or line.is_bold,
            )
            continue

        groups.append(
            _NativeTextGroup(
                text=line.text,
                rectangle=line.rectangle,
                block=line.block,
                first_line=line.line,
                font_size=line.font_size,
                is_bold=line.is_bold,
            )
        )

    return sorted(
        groups,
        key=lambda item: (
            item.rectangle.top,
            item.rectangle.left,
            item.block,
            item.first_line,
        ),
    )


def _is_wrapped_line(
    group: _NativeTextGroup,
    line: _NativeTextLine,
) -> bool:
    if group.block != line.block:
        return False

    vertical_gap = line.rectangle.top - group.rectangle.bottom
    return (
        -2 <= vertical_gap <= _WRAPPED_LINE_GAP
        and _horizontal_overlap_ratio(group.rectangle, line.rectangle) >= 0.25
    )


def _question_group(
    widget: _Rectangle,
    groups: list[_NativeTextGroup],
) -> Optional[_NativeTextGroup]:
    candidates: list[tuple[float, _NativeTextGroup]] = []

    for group in groups:
        if _is_heading(group):
            continue

        vertical_gap = widget.top - group.rectangle.bottom
        if (
            0 <= vertical_gap <= _QUESTION_VERTICAL_GAP
            and _horizontal_overlap_ratio(widget, group.rectangle) >= 0.5
        ):
            horizontal_offset = abs(widget.left - group.rectangle.left)
            candidates.append(
                (vertical_gap + horizontal_offset * 0.02, group)
            )

        right_gap = group.rectangle.left - widget.right
        if (
            0 <= right_gap <= _QUESTION_VERTICAL_GAP
            and _vertical_overlap_ratio(widget, group.rectangle) >= 0.25
        ):
            vertical_offset = abs(
                _rectangle_center_y(widget)
                - _rectangle_center_y(group.rectangle)
            )
            candidates.append((right_gap + vertical_offset * 0.1, group))

        left_gap = widget.left - group.rectangle.right
        if (
            0 <= left_gap <= _QUESTION_VERTICAL_GAP
            and _vertical_overlap_ratio(widget, group.rectangle) >= 0.25
        ):
            vertical_offset = abs(
                _rectangle_center_y(widget)
                - _rectangle_center_y(group.rectangle)
            )
            candidates.append((left_gap + vertical_offset * 0.1, group))

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1].rectangle.top,
            item[1].rectangle.left,
        )
    )
    best_score, best_group = candidates[0]
    if (
        len(candidates) > 1
        and abs(candidates[1][0] - best_score) < 1.5
        and candidates[1][1].text != best_group.text
    ):
        return None
    return best_group


def _field_help_text(
    widget: _Rectangle,
    groups: list[_NativeTextGroup],
    question_group: Optional[_NativeTextGroup],
) -> Optional[str]:
    candidates: list[tuple[float, _NativeTextGroup]] = []

    for group in groups:
        if group == question_group or _is_heading(group):
            continue
        if _HELP_TEXT_PATTERN.search(group.text) is None:
            continue

        vertical_gap = group.rectangle.top - widget.bottom
        if not 0 <= vertical_gap <= _HELP_VERTICAL_GAP:
            continue
        if _horizontal_overlap_ratio(widget, group.rectangle) < 0.25:
            continue

        candidates.append(
            (
                vertical_gap
                + abs(widget.left - group.rectangle.left) * 0.01,
                group,
            )
        )

    if not candidates:
        return None

    _, group = min(
        candidates,
        key=lambda item: (
            item[0],
            item[1].rectangle.top,
            item[1].rectangle.left,
        ),
    )
    return _clean_context_text(group.text)


def _field_section(
    widget: _Rectangle,
    groups: list[_NativeTextGroup],
) -> Optional[str]:
    headings = [
        group
        for group in groups
        if group.rectangle.bottom <= widget.top and _is_heading(group)
    ]
    if not headings:
        return None

    heading = max(
        headings,
        key=lambda item: (
            item.rectangle.bottom,
            item.rectangle.left,
        ),
    )
    return _clean_context_text(heading.text)


def _page_title(
    groups: list[_NativeTextGroup],
    page_height: float,
) -> Optional[str]:
    top_groups = [
        group
        for group in groups
        if group.rectangle.top <= page_height * 0.2
        and len(group.text.split()) >= 2
    ]
    if not top_groups:
        return None

    prominent_groups = [
        group for group in top_groups if group.font_size >= 14
    ]
    candidates = prominent_groups or top_groups
    title = min(
        candidates,
        key=lambda item: (
            item.rectangle.top,
            item.rectangle.left,
        ),
    )
    return _clean_context_text(title.text)


def _page_instructions(
    groups: list[_NativeTextGroup],
    page_title: Optional[str],
    widget_rectangles: list[_Rectangle],
    page_height: float,
) -> list[str]:
    first_widget_top = min(
        (rectangle.top for rectangle in widget_rectangles),
        default=page_height * 0.45,
    )
    instruction_area_bottom = max(first_widget_top, page_height * 0.25)
    question_groups = [
        question_group
        for rectangle in widget_rectangles
        if (question_group := _question_group(rectangle, groups)) is not None
    ]
    instructions = []

    for group in groups:
        if group.rectangle.bottom > instruction_area_bottom:
            continue
        if _is_heading(group) or group in question_groups:
            continue

        text = _clean_context_text(group.text)
        if text == page_title or _INSTRUCTION_TEXT_PATTERN.search(text) is None:
            continue
        if text not in instructions:
            instructions.append(text)

    return instructions


def _field_page_context(
    page_title: Optional[str],
    section: Optional[str],
) -> Optional[str]:
    context_parts = []
    for part in (page_title, section):
        if part and part not in context_parts:
            context_parts.append(part)
    if not context_parts:
        return None
    return _bounded_context_text(" — ".join(context_parts))


def _is_heading(group: _NativeTextGroup) -> bool:
    text = group.text.strip()
    word_count = len(text.split())
    return bool(
        _HEADING_PATTERN.search(text)
        or (group.font_size >= 14 and word_count <= 20)
        or (
            group.is_bold
            and group.font_size >= 9
            and word_count <= 18
            and len(text) <= 200
        )
    )


def _clean_context_text(text: str) -> str:
    cleaned = " ".join(text.split())
    cleaned = re.sub(r"\s+([,.;:?!])", r"\1", cleaned)
    cleaned = re.sub(r"\s+\*$", "", cleaned).strip()
    return _bounded_context_text(cleaned)


def _bounded_context_text(text: str) -> str:
    if len(text) <= _MAX_CONTEXT_TEXT_LENGTH:
        return text
    return f"{text[:_MAX_CONTEXT_TEXT_LENGTH - 1].rstrip()}…"


def _pymupdf_rectangle(rectangle: pymupdf.Rect) -> _Rectangle:
    return _Rectangle(
        left=float(rectangle.x0),
        top=float(rectangle.y0),
        right=float(rectangle.x1),
        bottom=float(rectangle.y1),
    )


def _coordinates_rectangle(
    coordinates: Any,
) -> Optional[_Rectangle]:
    if coordinates is None or len(coordinates) < 4:
        return None
    return _Rectangle(
        left=float(coordinates[0]),
        top=float(coordinates[1]),
        right=float(coordinates[2]),
        bottom=float(coordinates[3]),
    )


def _bounding_rectangle(rectangles: list[_Rectangle]) -> _Rectangle:
    return _Rectangle(
        left=min(rectangle.left for rectangle in rectangles),
        top=min(rectangle.top for rectangle in rectangles),
        right=max(rectangle.right for rectangle in rectangles),
        bottom=max(rectangle.bottom for rectangle in rectangles),
    )


def _rectangles_intersect(
    first: _Rectangle,
    second: _Rectangle,
) -> bool:
    return (
        min(first.right, second.right) > max(first.left, second.left)
        and min(first.bottom, second.bottom) > max(first.top, second.top)
    )


def _horizontal_overlap_ratio(
    first: _Rectangle,
    second: _Rectangle,
) -> float:
    overlap = max(
        0.0,
        min(first.right, second.right) - max(first.left, second.left),
    )
    minimum_width = min(first.width, second.width)
    return overlap / minimum_width if minimum_width > 0 else 0.0


def _vertical_overlap_ratio(
    first: _Rectangle,
    second: _Rectangle,
) -> float:
    overlap = max(
        0.0,
        min(first.bottom, second.bottom) - max(first.top, second.top),
    )
    minimum_height = min(first.height, second.height)
    return overlap / minimum_height if minimum_height > 0 else 0.0


def _rectangle_center_y(rectangle: _Rectangle) -> float:
    return (rectangle.top + rectangle.bottom) / 2


def _field_widget_locations(reader: PdfReader) -> dict[str, _WidgetLocation]:
    locations: dict[str, _WidgetLocation] = {}
    visual_order = 0

    for page_number, page in enumerate(reader.pages, start=1):
        positions = []
        for annotation_order, annotation in enumerate(page.get("/Annots", [])):
            widget = annotation.get_object()
            if str(widget.get("/Subtype")) != "/Widget":
                continue

            field_id = _qualified_field_name(widget)
            rectangle = widget.get("/Rect")
            if not field_id or rectangle is None or len(rectangle) < 4:
                continue

            coordinates = [float(coordinate) for coordinate in rectangle[:4]]
            positions.append(
                _WidgetPosition(
                    field_id=field_id,
                    top=max(coordinates[1], coordinates[3]),
                    left=min(coordinates[0], coordinates[2]),
                    annotation_order=annotation_order,
                )
            )

        for row in _visual_rows(positions):
            for position in sorted(
                row,
                key=lambda item: (item.left, item.annotation_order),
            ):
                locations.setdefault(
                    position.field_id,
                    _WidgetLocation(page=page_number, order=visual_order),
                )
                visual_order += 1

    return locations


def _visual_rows(
    positions: list[_WidgetPosition],
) -> list[list[_WidgetPosition]]:
    rows: list[list[_WidgetPosition]] = []
    row_tops: list[float] = []

    for position in sorted(
        positions,
        key=lambda item: (-item.top, item.left, item.annotation_order),
    ):
        if (
            not rows
            or abs(row_tops[-1] - position.top) > _VISUAL_ROW_TOLERANCE
        ):
            rows.append([position])
            row_tops.append(position.top)
        else:
            rows[-1].append(position)

    return rows


def _qualified_field_name(widget: dict[str, Any]) -> str:
    names = []
    current: Optional[dict[str, Any]] = widget
    while current is not None:
        partial_name = current.get("/T")
        if partial_name is not None:
            names.append(str(partial_name))
        parent_reference = current.get("/Parent")
        current = parent_reference.get_object() if parent_reference else None
    return ".".join(reversed(names))


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
