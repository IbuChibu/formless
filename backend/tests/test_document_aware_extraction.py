from dataclasses import asdict
from pathlib import Path

import pytest

from app.services.pdf_service import PdfField, extract_acroform_fields


fixtures_path = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("relative_path", "field_id", "expected_question", "expected_section"),
    [
        (
            "sample_form.pdf",
            "full_name",
            "Full name",
            "Sample application",
        ),
        (
            "household_support_review_demo.pdf",
            "primary_support_category",
            "Primary category of support sought",
            "C. Present circumstances and requested support",
        ),
        (
            "real_world/uscis_i9_2025.pdf",
            "Last Name (Family Name)",
            "Last Name (Family Name)",
            (
                "Section 1. Employee Information and Attestation: Employees "
                "must complete and sign Section 1 of Form I-9 no later than "
                "the first day of employment, but not before accepting a job "
                "offer."
            ),
        ),
        (
            "real_world/sba_startup_costs_2023.pdf",
            "One-time budget cost 1",
            "Rent Budget amount 1, edit to change amount",
            "Rent",
        ),
    ],
)
def test_grounding_is_deterministic_across_supported_fixtures(
    relative_path: str,
    field_id: str,
    expected_question: str,
    expected_section: str,
) -> None:
    pdf_data = (fixtures_path / relative_path).read_bytes()

    first_extraction = extract_acroform_fields(pdf_data)
    second_extraction = extract_acroform_fields(pdf_data)

    assert [asdict(field) for field in first_extraction] == [
        asdict(field) for field in second_extraction
    ]

    field = _field_by_id(first_extraction, field_id)
    assert field.question == expected_question
    assert field.section == expected_section
    assert field.page_context is not None


def test_visible_question_and_help_text_are_grounded_separately() -> None:
    fields = extract_acroform_fields(
        (fixtures_path / "household_support_review_demo.pdf").read_bytes()
    )

    address = _field_by_id(fields, "ordinary_residence_address")
    assert address.label == (
        "The address where you normally live, even if you are temporarily away"
    )
    assert address.question == (
        "Address at which you are ordinarily resident "
        "(not merely a correspondence address)"
    )
    assert address.help_text == (
        "For this demonstration, 'ordinary residence' means the place you "
        "normally live. A temporary absence does not necessarily change it."
    )
    assert address.page_context == (
        "Household Stability Support Review — "
        "A. Applicant and ordinary residence"
    )


@pytest.mark.parametrize(
    ("relative_path", "field_id", "stored_value"),
    [
        ("sample_form.pdf", "country", "United Kingdom"),
        (
            "household_support_review_demo.pdf",
            "primary_support_category",
            "Select one",
        ),
        (
            "real_world/sba_startup_costs_2023.pdf",
            "One-time rent expense 1",
            "Security deposit",
        ),
        (
            "real_world/sba_startup_costs_2023.pdf",
            "One-time budget cost 1",
            "1200",
        ),
    ],
)
def test_widget_values_are_not_used_as_document_context(
    relative_path: str,
    field_id: str,
    stored_value: str,
) -> None:
    fields = extract_acroform_fields(
        (fixtures_path / relative_path).read_bytes()
    )
    field = _field_by_id(fields, field_id)

    assert field.value == stored_value
    context = " ".join(
        value
        for value in (
            field.question,
            field.help_text,
            field.section,
            field.page_context,
        )
        if value is not None
    )
    assert stored_value not in context


def test_ambiguous_question_falls_back_to_existing_field_label() -> None:
    fields = extract_acroform_fields(
        (
            fixtures_path
            / "real_world"
            / "sba_startup_costs_2023.pdf"
        ).read_bytes()
    )

    field = _field_by_id(fields, "One-time budget cost 1")
    assert field.question == field.label


def _field_by_id(fields: list[PdfField], field_id: str) -> PdfField:
    return next(field for field in fields if field.id == field_id)
