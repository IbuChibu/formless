from __future__ import annotations

import json
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app


client = TestClient(app)
fixture_path = (
    Path(__file__).parent / "fixtures" / "real_world" / "uscis_i9_2025.pdf"
)


def test_extract_uscis_i9_returns_only_terminal_fields() -> None:
    response = client.post(
        "/pdf/extract",
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    fields = response.json()["fields"]
    fields_by_id = {field["id"]: field for field in fields}

    assert len(fields) == 128
    assert Counter(field["type"] for field in fields) == {
        "text": 111,
        "textarea": 4,
        "dropdown": 5,
        "checkbox": 8,
    }
    assert "List A" not in fields_by_id
    assert fields_by_id["Last Name Family Name from Section 1"]["type"] == "text"
    assert fields_by_id["Additional Information"]["type"] == "textarea"
    assert fields_by_id["CB_1"]["type"] == "checkbox"
    assert "CA" in fields_by_id["State"]["options"]


def test_fill_uscis_i9_updates_all_supported_fields_and_preserves_source() -> None:
    original_pdf = fixture_path.read_bytes()
    extraction_response = client.post(
        "/pdf/extract",
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )
    fields = extraction_response.json()["fields"]
    values = {
        field["id"]: _test_value(field)
        for field in fields
    }

    response = client.post(
        "/pdf/fill",
        data={"values": json.dumps(values)},
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content != original_pdf
    assert fixture_path.read_bytes() == original_pdf

    reader = PdfReader(BytesIO(response.content), strict=False)
    stored_fields = reader.get_fields() or {}

    for field_id, expected in values.items():
        stored_value = str(stored_fields[field_id].get("/V"))
        assert stored_value == _expected_pdf_value(field_id, expected)

    assert str(stored_fields["Additional Information"]["/V"]) == "X"
    assert str(stored_fields["State"]["/V"]) == "AK"
    assert str(stored_fields["CB_1"]["/V"]) == "/On"
    assert str(
        stored_fields["List A.  Document 2. Expiration Date (if any)"]["/V"]
    ) == "X"

    widgets = _widgets(reader)
    assert len(widgets) == 130
    assert sum(
        _qualified_field_name(widget) == "Document Title 1"
        for widget in widgets
    ) == 2

    for widget in widgets:
        field_id = _qualified_field_name(widget)
        assert field_id in values
        assert _effective_value(widget) == _expected_pdf_value(
            field_id,
            values[field_id],
        )
        _assert_non_empty_appearance(widget)


def _test_value(field: dict[str, Any]) -> str | bool:
    if field["type"] in {"text", "textarea"}:
        return "X"
    if field["type"] == "dropdown":
        return next(option for option in field["options"] if option.strip())
    return field["id"] == "CB_1"


def _expected_pdf_value(field_id: str, value: str | bool) -> str:
    if isinstance(value, bool):
        if not value:
            return "/Off"
        return "/On" if field_id.startswith("CB_") else "/Yes"
    return value


def _widgets(reader: PdfReader) -> list[dict[str, Any]]:
    return [
        annotation.get_object()
        for page in reader.pages
        for annotation in page.get("/Annots", [])
        if str(annotation.get_object().get("/Subtype")) == "/Widget"
    ]


def _qualified_field_name(widget: dict[str, Any]) -> str:
    names = []
    current = widget
    while current:
        partial_name = current.get("/T")
        if partial_name is not None:
            names.append(str(partial_name))
        parent_reference = current.get("/Parent")
        current = parent_reference.get_object() if parent_reference else None
    return ".".join(reversed(names))


def _effective_value(widget: dict[str, Any]) -> str:
    current = widget
    while current:
        value = current.get("/V")
        if value is not None:
            return str(value)
        parent_reference = current.get("/Parent")
        current = parent_reference.get_object() if parent_reference else None
    raise AssertionError("Widget has no effective value")


def _assert_non_empty_appearance(widget: dict[str, Any]) -> None:
    normal_appearance = widget["/AP"]["/N"].get_object()
    if hasattr(normal_appearance, "get_data"):
        assert normal_appearance.get_data()
        return
    appearance_state = widget["/AS"]
    if appearance_state == "/Off" and appearance_state not in normal_appearance:
        return
    assert normal_appearance[appearance_state].get_object().get_data()
