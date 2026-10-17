import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app


client = TestClient(app)
fixtures = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("relative_path", "field_id", "value", "stored_value"),
    [
        ("sample_form.pdf", "full_name", "Milestone Nine", "Milestone Nine"),
        (
            "household_support_review_demo.pdf",
            "applicant_full_legal_name",
            "Milestone Nine",
            "Milestone Nine",
        ),
        (
            "real_world/sba_startup_costs_2023.pdf",
            "Monthly rent expense 1",
            "1250",
            "1250",
        ),
        (
            "real_world/state_ds11_2025.pdf",
            "Selection",
            "U.S. Passport Book",
            "/Book",
        ),
        (
            "real_world/uscis_i9_2025.pdf",
            "Last Name (Family Name)",
            "Example",
            "Example",
        ),
    ],
    ids=["sample", "household", "sba", "ds11", "i9"],
)
def test_supported_fixture_completes_extract_to_download_workflow(
    relative_path: str,
    field_id: str,
    value: str,
    stored_value: str,
) -> None:
    fixture_path = fixtures / relative_path
    original_pdf = fixture_path.read_bytes()

    extraction_response = client.post(
        "/pdf/extract",
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )

    assert extraction_response.status_code == 200
    extracted_fields = {
        field["id"]: field for field in extraction_response.json()["fields"]
    }
    assert field_id in extracted_fields
    assert extracted_fields[field_id]["supported"] is True
    assert extracted_fields[field_id]["editable"] is True

    fill_response = client.post(
        "/pdf/fill",
        data={"values": json.dumps({field_id: value})},
        files={"file": (fixture_path.name, original_pdf, "application/pdf")},
    )

    assert fill_response.status_code == 200
    assert fill_response.headers["content-type"] == "application/pdf"
    assert fill_response.content.startswith(b"%PDF")
    assert fill_response.content != original_pdf
    assert fixture_path.read_bytes() == original_pdf

    completed_fields = PdfReader(BytesIO(fill_response.content)).get_fields() or {}
    assert str(completed_fields[field_id]["/V"]) == stored_value
