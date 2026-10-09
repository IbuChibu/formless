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
    Path(__file__).parent
    / "fixtures"
    / "real_world"
    / "sba_startup_costs_2023.pdf"
)

calculated_field_ids = {
    "Total one-time actual costs",
    "Total monthly budget",
    "Total monthly actual costs",
    "Total one-time budget",
    "Total funds required",
}


def test_extract_sba_worksheet_returns_editable_fields_with_values() -> None:
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

    assert len(fields) == 93
    assert Counter(field["type"] for field in fields) == {
        "number": 62,
        "text": 31,
    }
    assert calculated_field_ids.isdisjoint(fields_by_id)
    assert fields_by_id["One-time rent expense 1"]["value"] == (
        "Security deposit"
    )
    assert fields_by_id["One-time budget cost 1"] == {
        "id": "One-time budget cost 1",
        "label": "Rent Budget amount 1, edit to change amount",
        "type": "number",
        "question": "Rent Budget amount 1, edit to change amount",
        "page": 1,
        "value": "1200",
        "section": "Rent",
        "page_context": "Startup costs — Joe’s Pizza Place — Rent",
    }
    assert fields_by_id["One-time actual cost 1"] == {
        "id": "One-time actual cost 1",
        "label": "Rent Actual amount 1, edit to change amount",
        "type": "number",
        "question": "Rent Actual amount 1, edit to change amount",
        "page": 1,
        "section": "Rent",
        "page_context": "Startup costs — Joe’s Pizza Place — Rent",
    }


def test_fill_sba_worksheet_recalculates_and_formats_totals() -> None:
    original_pdf = fixture_path.read_bytes()
    submitted_values = {
        "One-time budget cost 1": "2000",
        "One-time actual cost 1": "500",
        "Monthly budget cost 1": "1500",
        "Monthly actual cost 1": "800",
    }

    response = client.post(
        "/pdf/fill",
        data={"values": json.dumps(submitted_values)},
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content != original_pdf
    assert fixture_path.read_bytes() == original_pdf

    reader = PdfReader(BytesIO(response.content), strict=False)
    fields = reader.get_fields() or {}
    expected_values = {
        **submitted_values,
        "Total one-time budget": "10650",
        "Total one-time actual costs": "500",
        "Total monthly budget": "9425",
        "Total monthly actual costs": "800",
        "Total funds required": "20075",
    }
    expected_appearances = {
        field_id: f"{float(value):,.2f}"
        for field_id, value in expected_values.items()
    }

    assert len(fields) == 98
    for field_id, expected_value in expected_values.items():
        assert str(fields[field_id].get("/V")) == expected_value

    widgets = _widgets_by_id(reader)
    assert len(widgets) == 98
    for field_id, expected_appearance in expected_appearances.items():
        widget = widgets[field_id]
        assert str(widget.get("/V")) == expected_values[field_id]
        appearance = widget["/AP"]["/N"].get_object().get_data()
        assert expected_appearance.encode() in appearance

    for field_id in calculated_field_ids:
        calculation_action = fields[field_id]["/AA"]["/C"].get_object()
        assert str(calculation_action["/S"]) == "/JavaScript"


def test_fill_sba_worksheet_updates_all_editable_fields_in_one_request() -> None:
    original_pdf = fixture_path.read_bytes()
    extraction_response = client.post(
        "/pdf/extract",
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )
    fields = extraction_response.json()["fields"]
    submitted_values = {
        field["id"]: "1" if field["type"] == "number" else "X"
        for field in fields
    }

    response = client.post(
        "/pdf/fill",
        data={"values": json.dumps(submitted_values)},
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )

    assert response.status_code == 200
    assert fixture_path.read_bytes() == original_pdf

    reader = PdfReader(BytesIO(response.content), strict=False)
    stored_fields = reader.get_fields() or {}
    for field_id, expected_value in submitted_values.items():
        assert str(stored_fields[field_id].get("/V")) == expected_value

    expected_totals = {
        "Total one-time budget": "14",
        "Total one-time actual costs": "14",
        "Total monthly budget": "17",
        "Total monthly actual costs": "17",
        "Total funds required": "31",
    }
    for field_id, expected_value in expected_totals.items():
        assert str(stored_fields[field_id].get("/V")) == expected_value

    for widget in _widgets_by_id(reader).values():
        assert widget["/AP"]["/N"].get_object().get_data()


def test_fill_sba_worksheet_rejects_invalid_numeric_value() -> None:
    response = client.post(
        "/pdf/fill",
        data={
            "values": json.dumps(
                {"One-time actual cost 1": "five hundred"}
            )
        },
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Field 'One-time actual cost 1' requires a numeric value"
    }

    malformed_grouping_response = client.post(
        "/pdf/fill",
        data={"values": json.dumps({"One-time actual cost 1": "1,2"})},
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "application/pdf",
            )
        },
    )
    assert malformed_grouping_response.status_code == 422


def test_fill_sba_worksheet_rejects_direct_total_update() -> None:
    response = client.post(
        "/pdf/fill",
        data={"values": json.dumps({"Total funds required": "1"})},
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": (
            "Calculated PDF fields cannot be set directly: "
            "Total funds required"
        )
    }


def _widgets_by_id(reader: PdfReader) -> dict[str, dict[str, Any]]:
    return {
        str(widget["/T"]): widget
        for page in reader.pages
        for annotation in page.get("/Annots", [])
        if str((widget := annotation.get_object()).get("/Subtype")) == "/Widget"
    }
