from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from app.services.pdf_service import (
    PdfFillingError,
    extract_acroform,
    fill_acroform_fields,
)
from app.main import app


DS11_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "real_world"
    / "state_ds11_2025.pdf"
)
RADIO_FLAG = 1 << 15
PUSH_BUTTON_FLAG = 1 << 16
client = TestClient(app)


def test_button_capabilities_are_derived_from_widgets_and_appearances() -> None:
    extraction = extract_acroform(_button_fixture())
    fields = {field.id: field for field in extraction.fields}

    assert fields["valid_checkbox"].type == "checkbox"
    assert fields["valid_checkbox"].supported is True
    assert fields["valid_checkbox"].editable is True

    assert fields["missing_appearance"].supported is False
    assert fields["missing_appearance"].editable is False
    assert "missing normal appearance" in (
        fields["missing_appearance"].capability_reason or ""
    )

    assert fields["off_only"].supported is False
    assert "no usable non-off export state" in (
        fields["off_only"].capability_reason or ""
    )

    assert fields["no_off_state"].supported is False
    assert "no usable off state" in (
        fields["no_off_state"].capability_reason or ""
    )

    assert fields["ambiguous_checkbox"].supported is False
    assert "ambiguous non-off export states" in (
        fields["ambiguous_checkbox"].capability_reason or ""
    )

    assert fields["inferred_radio"].type == "radio"
    assert fields["inferred_radio"].options == ["Red", "Blue"]
    assert fields["inferred_radio"].supported is True
    assert fields["inferred_radio"].editable is True

    assert fields["flagged_radio"].type == "radio"
    assert fields["flagged_radio"].options == ["One", "Two"]
    assert fields["flagged_radio"].supported is True

    assert fields["push_action"].type == "button"
    assert fields["push_action"].supported is False
    assert fields["push_action"].editable is False
    assert "not answerable" in (
        fields["push_action"].capability_reason or ""
    )


def test_supported_button_values_are_stored_on_fields_and_widgets() -> None:
    source = _button_fixture()
    completed = fill_acroform_fields(
        source,
        {
            "valid_checkbox": True,
            "inferred_radio": "Blue",
            "flagged_radio": "Two",
        },
    )

    assert completed != source
    reader = PdfReader(BytesIO(completed))
    fields = reader.get_fields() or {}
    assert str(fields["valid_checkbox"]["/V"]) == "/Yes"
    assert str(fields["inferred_radio"]["/V"]) == "/Blue"
    assert str(fields["flagged_radio"]["/V"]) == "/Two"

    widgets = _widgets_by_field_id(reader)
    assert str(widgets["valid_checkbox"][0]["/AS"]) == "/Yes"
    _assert_selected_group_state(widgets["inferred_radio"], "/Blue")
    _assert_selected_group_state(widgets["flagged_radio"], "/Two")

    for field_id in ("valid_checkbox", "inferred_radio", "flagged_radio"):
        for widget in widgets[field_id]:
            normal = widget["/AP"]["/N"].get_object()
            selected = normal[widget["/AS"]].get_object()
            assert selected.get_data()


@pytest.mark.parametrize(
    ("field_id", "value", "reason"),
    [
        ("missing_appearance", True, "missing normal appearance states"),
        ("off_only", True, "no usable non-off export state"),
        ("no_off_state", True, "no usable off state"),
        ("ambiguous_checkbox", True, "ambiguous non-off export states"),
        ("push_action", True, "not answerable"),
    ],
)
def test_fill_rejects_unsupported_button_controls(
    field_id: str,
    value: str | bool,
    reason: str,
) -> None:
    with pytest.raises(PdfFillingError, match=reason):
        fill_acroform_fields(_button_fixture(), {field_id: value})


def test_fill_rejects_unknown_radio_export_value() -> None:
    with pytest.raises(
        PdfFillingError,
        match="Invalid option for field 'inferred_radio': Green",
    ):
        fill_acroform_fields(
            _button_fixture(),
            {"inferred_radio": "Green"},
        )


def test_ds11_selection_uses_actual_radio_options_and_push_is_unsupported() -> None:
    original = DS11_FIXTURE.read_bytes()
    response = client.post(
        "/pdf/extract",
        files={
            "file": (
                DS11_FIXTURE.name,
                original,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    fields = {field["id"]: field for field in response.json()["fields"]}
    assert fields["Selection"]["type"] == "radio"
    assert fields["Selection"]["options"] == [
        "U.S. Passport Book",
        "U.S. Passport Card",
        "Both",
    ]
    assert fields["Selection"]["supported"] is True
    assert fields["Selection"]["editable"] is True
    assert fields["Clear"]["type"] == "button"
    assert fields["Clear"]["supported"] is False
    assert fields["Clear"]["editable"] is False
    assert "not answerable" in fields["Clear"]["capability_reason"]

    completed = fill_acroform_fields(
        original,
        {"Selection": "U.S. Passport Book"},
    )
    assert DS11_FIXTURE.read_bytes() == original
    completed_fields = PdfReader(BytesIO(completed)).get_fields() or {}
    selection = completed_fields["Selection"]
    assert str(selection["/V"]) == "/Book"
    _assert_selected_group_state(
        [child.get_object() for child in selection["/Kids"]],
        "/Book",
    )

    with pytest.raises(PdfFillingError, match="not answerable"):
        fill_acroform_fields(original, {"Clear": True})


def _button_fixture() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    annotations = ArrayObject()
    fields = ArrayObject()
    page[NameObject("/Annots")] = annotations
    acroform = DictionaryObject(
        {
            NameObject("/Fields"): fields,
            NameObject("/NeedAppearances"): BooleanObject(False),
        }
    )
    writer.root_object[NameObject("/AcroForm")] = writer._add_object(acroform)

    _add_checkbox(
        writer,
        page,
        annotations,
        fields,
        "valid_checkbox",
        700,
        ("/Off", "/Yes"),
    )
    _add_checkbox(
        writer,
        page,
        annotations,
        fields,
        "missing_appearance",
        670,
        None,
    )
    _add_checkbox(
        writer,
        page,
        annotations,
        fields,
        "off_only",
        640,
        ("/Off",),
    )
    _add_checkbox(
        writer,
        page,
        annotations,
        fields,
        "no_off_state",
        625,
        ("/Yes",),
        current_state="/Yes",
    )
    _add_checkbox(
        writer,
        page,
        annotations,
        fields,
        "ambiguous_checkbox",
        610,
        ("/Off", "/Yes", "/Maybe"),
    )
    _add_radio_group(
        writer,
        page,
        annotations,
        fields,
        "inferred_radio",
        570,
        ("/Red", "/Blue"),
        flags=0,
    )
    _add_radio_group(
        writer,
        page,
        annotations,
        fields,
        "flagged_radio",
        530,
        ("/One", "/Two"),
        flags=RADIO_FLAG,
    )
    _add_push_button(
        writer,
        page,
        annotations,
        fields,
        "push_action",
        490,
    )

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _add_checkbox(
    writer: PdfWriter,
    page: DictionaryObject,
    annotations: ArrayObject,
    fields: ArrayObject,
    field_id: str,
    top: float,
    states: Optional[tuple[str, ...]],
    *,
    current_state: str = "/Off",
) -> None:
    widget = _widget_dictionary(page, field_id, top)
    widget[NameObject("/FT")] = NameObject("/Btn")
    widget[NameObject("/AS")] = NameObject(current_state)
    if states is not None:
        widget[NameObject("/AP")] = _state_appearance(writer, states)
    reference = writer._add_object(widget)
    annotations.append(reference)
    fields.append(reference)


def _add_radio_group(
    writer: PdfWriter,
    page: DictionaryObject,
    annotations: ArrayObject,
    fields: ArrayObject,
    field_id: str,
    top: float,
    states: tuple[str, ...],
    *,
    flags: int,
) -> None:
    parent = DictionaryObject(
        {
            NameObject("/FT"): NameObject("/Btn"),
            NameObject("/Ff"): NumberObject(flags),
            NameObject("/T"): TextStringObject(field_id),
        }
    )
    parent_reference = writer._add_object(parent)
    kids = ArrayObject()
    for index, state in enumerate(states):
        widget = _widget_dictionary(page, None, top - index * 20)
        widget[NameObject("/Parent")] = parent_reference
        widget[NameObject("/AS")] = NameObject("/Off")
        widget[NameObject("/AP")] = _state_appearance(
            writer,
            ("/Off", state),
        )
        reference = writer._add_object(widget)
        annotations.append(reference)
        kids.append(reference)
    parent[NameObject("/Kids")] = kids
    fields.append(parent_reference)


def _add_push_button(
    writer: PdfWriter,
    page: DictionaryObject,
    annotations: ArrayObject,
    fields: ArrayObject,
    field_id: str,
    top: float,
) -> None:
    widget = _widget_dictionary(page, field_id, top)
    widget[NameObject("/FT")] = NameObject("/Btn")
    widget[NameObject("/Ff")] = NumberObject(PUSH_BUTTON_FLAG)
    widget[NameObject("/AP")] = DictionaryObject(
        {NameObject("/N"): _appearance_stream(writer)}
    )
    reference = writer._add_object(widget)
    annotations.append(reference)
    fields.append(reference)


def _widget_dictionary(
    page: DictionaryObject,
    field_id: Optional[str],
    top: float,
) -> DictionaryObject:
    widget = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/Rect"): ArrayObject(
                [
                    FloatObject(72),
                    FloatObject(top),
                    FloatObject(90),
                    FloatObject(top + 18),
                ]
            ),
            NameObject("/P"): page.indirect_reference,
        }
    )
    if field_id is not None:
        widget[NameObject("/T")] = TextStringObject(field_id)
    return widget


def _state_appearance(
    writer: PdfWriter,
    states: tuple[str, ...],
) -> DictionaryObject:
    return DictionaryObject(
        {
            NameObject("/N"): DictionaryObject(
                {
                    NameObject(state): _appearance_stream(writer)
                    for state in states
                }
            )
        }
    )


def _appearance_stream(writer: PdfWriter):
    stream = DecodedStreamObject()
    stream.set_data(b"q 0 0 10 10 re S Q")
    stream.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject(
                [FloatObject(0), FloatObject(0), FloatObject(10), FloatObject(10)]
            ),
        }
    )
    return writer._add_object(stream)


def _widgets_by_field_id(
    reader: PdfReader,
) -> dict[str, list[DictionaryObject]]:
    grouped: dict[str, list[DictionaryObject]] = {}
    for page in reader.pages:
        for annotation in page.get("/Annots", []):
            widget = annotation.get_object()
            if str(widget.get("/Subtype")) != "/Widget":
                continue
            current = widget
            while current.get("/T") is None and current.get("/Parent"):
                current = current["/Parent"].get_object()
            grouped.setdefault(str(current["/T"]), []).append(widget)
    return grouped


def _assert_selected_group_state(
    widgets: list[DictionaryObject],
    selected_state: str,
) -> None:
    states = [str(widget["/AS"]) for widget in widgets]
    assert states.count(selected_state) == 1
    assert all(state in {selected_state, "/Off"} for state in states)
