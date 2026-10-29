from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Optional, Union

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.deepgram_service import (
    DeepgramConfigurationError,
    DeepgramService,
    DeepgramServiceError,
)
from app.services.form_agent import (
    FormAgentError,
    FormAgentRequest,
    FormAgentResponse,
    FormAgentService,
    FormAgentTransitionError,
)
from app.services.nemotron_service import (
    NemotronConfigurationError,
    NemotronService,
    NemotronServiceError,
)
from app.services.pdf_service import (
    PdfExtractionError,
    PdfFillingError,
    extract_acroform,
    fill_acroform_fields,
)
from app.services.tavily_service import (
    TavilyConfigurationError,
    TavilyService,
    TavilyServiceError,
)


PdfFieldValue = Union[str, bool]


class HealthResponse(BaseModel):
    status: str
    service: str


class DeepgramTokenResponse(BaseModel):
    access_token: str
    expires_in: int = Field(gt=0, le=3600)


class PdfWidgetGeometryResponse(BaseModel):
    page: int = Field(ge=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class PdfFieldResponse(BaseModel):
    id: str
    label: str
    type: str
    question: str
    supported: bool
    editable: bool
    page: Optional[int] = None
    options: Optional[list[str]] = None
    value: Optional[PdfFieldValue] = None
    capability_reason: Optional[str] = None
    help_text: Optional[str] = None
    section: Optional[str] = None
    page_context: Optional[str] = None
    widgets: list[PdfWidgetGeometryResponse] = Field(default_factory=list)


class PdfFormContextResponse(BaseModel):
    title: Optional[str] = None
    instructions: list[str] = Field(default_factory=list)
    form_id: Optional[str] = None
    form_version: Optional[str] = None


class PdfExtractionResponse(BaseModel):
    fields: list[PdfFieldResponse]
    form_context: PdfFormContextResponse


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
            detail=(
                "Nebius Token Factory is not configured. Load backend/.env "
                "before starting the API, or continue with manual PDF editing."
            ),
        ) from error


def get_deepgram_service() -> DeepgramService:
    try:
        return DeepgramService.from_environment()
    except DeepgramConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Deepgram voice input is not configured. Add the server-side "
                "credential to backend/.env, or continue by typing."
            ),
        ) from error


def get_tavily_service() -> TavilyService:
    return TavilyService.from_optional_environment()


def get_form_agent_service(
    nemotron_service: NemotronService = Depends(get_nemotron_service),
    tavily_service: TavilyService = Depends(get_tavily_service),
) -> FormAgentService:
    return FormAgentService(nemotron_service, tavily_service)


@app.post("/voice/deepgram/token", response_model=DeepgramTokenResponse)
async def create_deepgram_token(
    service: DeepgramService = Depends(get_deepgram_service),
) -> DeepgramTokenResponse:
    try:
        token = await service.issue_temporary_token()
    except DeepgramServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return DeepgramTokenResponse(
        access_token=token.access_token,
        expires_in=token.expires_in,
    )


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


@app.post("/agent/respond", response_model=FormAgentResponse)
async def respond_to_form_agent(
    request: FormAgentRequest,
    service: FormAgentService = Depends(get_form_agent_service),
) -> FormAgentResponse:
    try:
        return await service.respond(request)
    except FormAgentTransitionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except TavilyConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (FormAgentError, NemotronServiceError, TavilyServiceError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post(
    "/pdf/extract",
    response_model=PdfExtractionResponse,
    response_model_exclude_none=True,
)
async def extract_pdf_fields(file: UploadFile = File(...)) -> PdfExtractionResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="File must be a PDF")

    try:
        extraction = extract_acroform(await file.read())
    except PdfExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return PdfExtractionResponse(
        fields=[
            PdfFieldResponse(
                id=field.id,
                label=field.label,
                type=field.type,
                question=field.question,
                supported=field.supported,
                editable=field.editable,
                page=field.page,
                options=field.options,
                value=field.value,
                capability_reason=field.capability_reason,
                help_text=field.help_text,
                section=field.section,
                page_context=field.page_context,
                widgets=[
                    PdfWidgetGeometryResponse(
                        page=widget.page,
                        x=widget.x,
                        y=widget.y,
                        width=widget.width,
                        height=widget.height,
                    )
                    for widget in field.widgets
                ],
            )
            for field in extraction.fields
        ],
        form_context=PdfFormContextResponse(
            title=extraction.form_context.title,
            instructions=list(extraction.form_context.instructions),
            form_id=extraction.form_context.form_id,
            form_version=extraction.form_context.form_version,
        ),
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
