from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.pdf_service import PdfExtractionError, extract_acroform_fields


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
