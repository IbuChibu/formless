from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.pdf_service import _field_label


client = TestClient(app)
fixture_path = (
    Path(__file__).parent / "fixtures" / "household_support_review_demo.pdf"
)


def test_demo_fields_follow_visible_question_order_and_pages() -> None:
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

    assert len(fields) == 29
    assert [field["id"] for field in fields[:8]] == [
        "applicant_full_legal_name",
        "applicant_preferred_name",
        "applicant_date_of_birth",
        "occupancy_start_date",
        "residency_arrangement",
        "ordinary_residence_address",
        "household_member_count",
        "shares_food_or_living_costs",
    ]
    assert fields[0]["label"] == (
        "Your full legal name as it appears on official records"
    )
    assert fields[0]["page"] == 1
    assert fields[14]["page"] == 1
    assert fields[15]["id"] == "primary_support_category"
    assert fields[15]["page"] == 2
    assert all(field["page"] in {1, 2} for field in fields)


def test_placeholder_alternate_name_falls_back_to_humanized_id() -> None:
    assert _field_label("emergency_contact_email", {"/TU": "undefined"}) == (
        "Emergency contact email"
    )
    assert _field_label("applicant.name", {"/TU": "  "}) == "Applicant name"
