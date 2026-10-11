from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import Any

import pymupdf
import pytest
from pypdf import PdfReader

from app.services.pdf_service import (
    PdfFillingError,
    extract_acroform,
    fill_acroform_fields,
)
from evaluations.form_agent_evaluation import agent_field_from_pdf
from evaluations.form_agent_transcript_evaluation import (
    run_transcript_evaluation,
    transcript_fixtures,
)


DS11_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "real_world"
    / "state_ds11_2025.pdf"
)
W9_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "real_world"
    / "irs_w9_2024.pdf"
)


def test_ds11_extracts_one_ordered_logical_field_per_question() -> None:
    extraction = extract_acroform(DS11_FIXTURE.read_bytes())
    fields = extraction.fields
    by_id = {field.id: field for field in fields}

    assert extraction.form_context.title == "Application for a U.S. Passport"
    assert extraction.form_context.form_id == "state-ds11"
    assert extraction.form_context.form_version == "04-2025"
    assert len(fields) == 84
    assert len(by_id) == len(fields)
    assert len({field.question for field in fields}) == len(fields)

    assert [field.id for field in fields[:10]] == [
        "Selection",
        "Regular or Large Book",
        "Applicant Last Name",
        "Applicant First Name",
        "Applicant Middle Name",
        "Applicant DOB M",
        "Applicant DOB D",
        "Applicant DOB Y",
        "Gender",
        "Applicant Place of Birth",
    ]
    assert [
        field.id
        for field in fields
        if field.id
        in {
            "Spouse US Citizen",
            "Date of Marriage (mm/dd/yyyy)",
            "Divorced",
            "Widow/Divorce Date (mm/dd/yyyy)",
        }
    ] == [
        "Spouse US Citizen",
        "Date of Marriage (mm/dd/yyyy)",
        "Divorced",
        "Widow/Divorce Date (mm/dd/yyyy)",
    ]
    assert [field.page for field in fields] == sorted(
        field.page for field in fields if field.page is not None
    )

    selection = by_id["Selection"]
    assert selection.type == "radio"
    assert selection.supported is True
    assert selection.editable is True
    assert selection.label == "Documents requested"
    assert selection.options == [
        "U.S. Passport Book",
        "U.S. Passport Card",
        "Both",
    ]
    assert selection.help_text == (
        "The U.S. Passport Card is not valid for international air travel."
    )

    book_size = by_id["Regular or Large Book"]
    assert book_size.options == [
        "Regular Book (Standard)",
        "Large Book (Non-Standard)",
    ]
    assert book_size.help_text == (
        "The large book is for frequent international travelers who need "
        "more visa pages."
    )

    applicant_last_name = by_id["Applicant Last Name"]
    assert applicant_last_name.label == "1. Name - Last"
    assert applicant_last_name.question == "1. Name - Last"
    assert applicant_last_name.help_text is None
    assert "large book" not in applicant_last_name.question.casefold()

    assert by_id["Emergency Contact City"].help_text is None
    assert by_id["Circumstances of lost/stolen book/card"].help_text == (
        "If your most recent passport book or card was lost or stolen, explain "
        "the loss or theft in detail in this field."
    )

    clear = by_id["Clear"]
    assert clear.type == "button"
    assert clear.supported is False
    assert clear.editable is False
    assert "not answerable" in (clear.capability_reason or "")


def test_ds11_schema_uses_the_existing_form_agent_validation_boundary() -> None:
    extraction = extract_acroform(DS11_FIXTURE.read_bytes())
    agent_fields = [
        agent_field
        for field in extraction.fields
        if (agent_field := agent_field_from_pdf(field)) is not None
    ]

    assert agent_fields
    assert agent_fields[0].id == "Applicant Last Name"
    assert agent_fields[0].question == "1. Name - Last"
    assert "Clear" not in {field.id for field in agent_fields}
    assert all(field.type != "radio" for field in agent_fields)
    assert all(
        option.strip()
        for field in agent_fields
        for option in (field.options or [])
    )


def test_ds11_fills_visible_choice_labels_and_text_without_changing_source() -> None:
    original = DS11_FIXTURE.read_bytes()
    completed = fill_acroform_fields(
        original,
        {
            "Selection": "U.S. Passport Book",
            "Regular or Large Book": "Large Book (Non-Standard)",
            "Applicant Last Name": "EXAMPLE",
        },
    )

    assert DS11_FIXTURE.read_bytes() == original
    assert completed != original

    reader = PdfReader(BytesIO(completed))
    fields = reader.get_fields() or {}
    assert str(fields["Selection"]["/V"]) == "/Book"
    assert str(fields["Regular or Large Book"]["/V"]) == "/Large"
    assert str(fields["Applicant Last Name"]["/V"]) == "EXAMPLE"

    widgets = _widgets_by_field_id(reader)
    _assert_selected_group_state(widgets["Selection"], "/Book")
    _assert_selected_group_state(
        widgets["Regular or Large Book"],
        "/Large",
    )
    text_appearance = widgets["Applicant Last Name"][0]["/AP"]["/N"]
    assert text_appearance.get_object().get_data()

    assert _rendered_widget(original, "Selection") != _rendered_widget(
        completed,
        "Selection",
    )
    assert _rendered_widget(
        original,
        "Applicant Last Name",
    ) != _rendered_widget(completed, "Applicant Last Name")


def test_ds11_fill_rejects_hidden_export_values_not_returned_by_extraction() -> None:
    with pytest.raises(
        PdfFillingError,
        match="Invalid option for field 'Selection': Book",
    ):
        fill_acroform_fields(
            DS11_FIXTURE.read_bytes(),
            {"Selection": "Book"},
        )


def test_ds11_typed_transcript_proposes_first_supported_applicant_field() -> None:
    transcript = next(
        transcript
        for transcript in transcript_fixtures()
        if transcript.name == "ds11-first-applicant-field"
    )
    report = asyncio.run(
        run_transcript_evaluation(transcripts=(transcript,))
    )

    assert report.failures == ()
    assert report.metrics.curated_transcript_completion_rate == 1.0
    completed = fill_acroform_fields(
        DS11_FIXTURE.read_bytes(),
        {"Applicant Last Name": "Example"},
    )
    fields = PdfReader(BytesIO(completed)).get_fields() or {}
    assert str(fields["Applicant Last Name"]["/V"]) == "Example"


def test_w9_hybrid_acroform_extraction_does_not_regress() -> None:
    extraction = extract_acroform(W9_FIXTURE.read_bytes())

    assert len(extraction.fields) == 23
    assert extraction.form_context.form_id is None
    assert extraction.fields[0].id == (
        "topmostSubform[0].Page1[0].f1_01[0]"
    )


def _widgets_by_field_id(
    reader: PdfReader,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for page in reader.pages:
        for annotation in page.get("/Annots", []):
            widget = annotation.get_object()
            if str(widget.get("/Subtype")) != "/Widget":
                continue
            names = []
            current = widget
            while current is not None:
                if current.get("/T") is not None:
                    names.append(str(current["/T"]))
                parent = current.get("/Parent")
                current = parent.get_object() if parent else None
            field_id = ".".join(reversed(names))
            grouped.setdefault(field_id, []).append(widget)
    return grouped


def _assert_selected_group_state(
    widgets: list[dict[str, Any]],
    selected_state: str,
) -> None:
    states = [str(widget["/AS"]) for widget in widgets]
    assert states.count(selected_state) == 1
    assert all(state in {selected_state, "/Off"} for state in states)


def _rendered_widget(pdf_data: bytes, field_id: str) -> bytes:
    document = pymupdf.open(stream=pdf_data, filetype="pdf")
    try:
        for page in document:
            for widget in page.widgets() or []:
                if widget.field_name != field_id:
                    continue
                rectangle = widget.rect + (-2, -2, 2, 2)
                return page.get_pixmap(
                    matrix=pymupdf.Matrix(2, 2),
                    clip=rectangle,
                    alpha=False,
                    annots=True,
                ).samples
    finally:
        document.close()
    raise AssertionError(f'Widget "{field_id}" was not found')
