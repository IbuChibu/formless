from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Optional, Union

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.nemotron_service import (
    NemotronConfigurationError,
    NemotronService,
    NemotronServiceError,
)
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
    label: str
    type: str
    page: Optional[int] = None
    options: Optional[list[str]] = None
    value: Optional[PdfFieldValue] = None


class PdfExtractionResponse(BaseModel):
    fields: list[PdfFieldResponse]


class FieldExplanationRequest(BaseModel):
    id: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=1000)
    type: str = Field(min_length=1, max_length=50)
    options: Optional[list[str]] = Field(default=None, max_length=100)
    form_context: Optional[str] = Field(default=None, max_length=2000)
    question: Optional[str] = Field(default=None, min_length=1, max_length=1000)


class FieldExplanationResponse(BaseModel):
    field_id: str
    explanation: str
    model: str


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


def get_nemotron_service() -> NemotronService:
    try:
        return NemotronService.from_environment()
    except NemotronConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="AI explanation service is not configured",
        ) from error


@app.post("/ai/explain", response_model=FieldExplanationResponse)
async def explain_field(
    field: FieldExplanationRequest,
    service: NemotronService = Depends(get_nemotron_service),
) -> FieldExplanationResponse:
    try:
        explanation = await service.explain_field(
            field_id=field.id,
            label=field.label,
            field_type=field.type,
            options=field.options,
            form_context=field.form_context,
            question=field.question,
        )
    except NemotronServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return FieldExplanationResponse(
        field_id=field.id,
        explanation=explanation,
        model=service.model,
    )


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
            PdfFieldResponse(
                id=field.id,
                label=field.label,
                type=field.type,
                page=field.page,
                options=field.options,
                value=field.value,
            )
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
