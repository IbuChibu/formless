from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Optional, Union

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.pdf_service import (
    PdfExtractionError,
    PdfFillingError,
    extract_acroform_fields,
    fill_acroform_fields,
)


PdfFieldValue = Union[str, bool]


class HealthResponse(BaseModel):
    status: str
    service: str


class PdfFieldResponse(BaseModel):
    id: str
    type: str
    options: Optional[list[str]] = None


class PdfExtractionResponse(BaseModel):
    fields: list[PdfFieldResponse]


app = FastAPI(title="Formless API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="formless-api")


@app.post(
    "/pdf/extract",
    response_model=PdfExtractionResponse,
    response_model_exclude_none=True,
)
async def extract_pdf_fields(file: UploadFile = File(...)) -> PdfExtractionResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="File must be a PDF")

    try:
        fields = extract_acroform_fields(await file.read())
    except PdfExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return PdfExtractionResponse(
        fields=[
            PdfFieldResponse(id=field.id, type=field.type, options=field.options)
            for field in fields
        ]
    )


@app.post(
    "/pdf/fill",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def fill_pdf(
    file: UploadFile = File(...),
    values: str = Form(...),
) -> Response:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="File must be a PDF")

    field_values = _parse_field_values(values)

    try:
        completed_pdf = fill_acroform_fields(await file.read(), field_values)
    except (PdfExtractionError, PdfFillingError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return Response(
        content=completed_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="completed-form.pdf"'},
    )


def _parse_field_values(raw_values: str) -> dict[str, PdfFieldValue]:
    try:
        values = json.loads(raw_values)
    except JSONDecodeError as error:
        raise HTTPException(
            status_code=422,
            detail="Values must be a JSON object of field IDs and values",
        ) from error

    if not isinstance(values, dict) or not values:
        raise HTTPException(
            status_code=422,
            detail="Values must be a non-empty JSON object",
        )

    if not all(isinstance(value, (str, bool)) for value in values.values()):
        raise HTTPException(
            status_code=422,
            detail="Field values must be strings or booleans",
        )

    return values
