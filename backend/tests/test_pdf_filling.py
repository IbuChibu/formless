import json
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app


client = TestClient(app)
fixture_path = Path(__file__).parent / "fixtures" / "sample_form.pdf"


def test_fill_pdf_returns_new_interactive_pdf_and_preserves_source() -> None:
    original_pdf = fixture_path.read_bytes()

    response = client.post(
        "/pdf/fill",
        data={
            "values": json.dumps(
                {
                    "full_name": "Ada Lovelace",
                    "country": "Other",
                    "accept_terms": True,
                }
            )
        },
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="completed-form.pdf"'
    )
    assert response.content != original_pdf
    assert fixture_path.read_bytes() == original_pdf

    reader = PdfReader(BytesIO(response.content))
    fields = reader.get_fields() or {}
    assert str(fields["full_name"]["/V"]) == "Ada Lovelace"
    assert str(fields["country"]["/V"]) == "Other"
    assert str(fields["accept_terms"]["/V"]) == "/Yes"

    expected_values = {
        "full_name": "Ada Lovelace",
        "country": "Other",
        "accept_terms": "/Yes",
    }
    widgets = [
        annotation.get_object()
        for page in reader.pages
        for annotation in page.get("/Annots", [])
        if str(annotation.get_object().get("/Subtype")) == "/Widget"
    ]
    assert len(widgets) == 3

    for widget in widgets:
        parent_reference = widget.get("/Parent")
        parent = parent_reference.get_object() if parent_reference else {}
        field_id = str(widget.get("/T") or parent.get("/T"))
        effective_value = widget.get("/V") or parent.get("/V")
        assert str(effective_value) == expected_values[field_id]

        normal_appearance = widget["/AP"]["/N"].get_object()
        if field_id == "accept_terms":
            selected_appearance = normal_appearance[widget["/AS"]].get_object()
            assert selected_appearance.get_data()
        else:
            assert normal_appearance.get_data()


def test_fill_pdf_rejects_unknown_field_ids() -> None:
    response = client.post(
        "/pdf/fill",
        data={"values": json.dumps({"missing_field": "value"})},
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown PDF field IDs: missing_field"}


def test_fill_pdf_rejects_invalid_choice_value() -> None:
    response = client.post(
        "/pdf/fill",
        data={"values": json.dumps({"country": "Atlantis"})},
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
        "detail": "Invalid option for field 'country': Atlantis"
    }


def test_fill_pdf_rejects_non_object_values() -> None:
    response = client.post(
        "/pdf/fill",
        data={"values": json.dumps(["not", "a", "mapping"])},
        files={
            "file": (
                fixture_path.name,
                fixture_path.read_bytes(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Values must be a non-empty JSON object"}
