from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
fixture_path = Path(__file__).parent / "fixtures" / "sample_form.pdf"


def test_extract_pdf_returns_acroform_fields() -> None:
    with fixture_path.open("rb") as fixture:
        response = client.post(
            "/pdf/extract",
            files={"file": (fixture_path.name, fixture, "application/pdf")},
        )

    assert response.status_code == 200

    fields = {field["id"]: field for field in response.json()["fields"]}
    assert fields == {
        "accept_terms": {
            "id": "accept_terms",
            "type": "checkbox",
            "value": False,
        },
        "country": {
            "id": "country",
            "type": "dropdown",
            "options": ["United Kingdom", "United States", "Other"],
            "value": "United Kingdom",
        },
        "full_name": {"id": "full_name", "type": "text", "value": ""},
    }


def test_extract_pdf_rejects_non_pdf_upload() -> None:
    response = client.post(
        "/pdf/extract",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "File must be a PDF"}


def test_extract_pdf_rejects_invalid_pdf_content() -> None:
    response = client.post(
        "/pdf/extract",
        files={"file": ("broken.pdf", b"%PDF-not-valid", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Uploaded file is not a valid PDF"}
