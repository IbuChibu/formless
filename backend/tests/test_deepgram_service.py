from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest

from app.main import app, get_deepgram_service
from app.services.deepgram_service import (
    DeepgramConfigurationError,
    DeepgramService,
    DeepgramServiceError,
    DeepgramSettings,
    DeepgramTemporaryToken,
)


LONG_LIVED_KEY = "long-lived-deepgram-secret"


def test_settings_require_server_side_key_and_hide_it_from_repr() -> None:
    with pytest.raises(DeepgramConfigurationError, match="not configured"):
        DeepgramSettings.from_environment({})

    settings = DeepgramSettings.from_environment(
        {
            "DEEPGRAM_API_KEY": LONG_LIVED_KEY,
            "DEEPGRAM_BASE_URL": "https://speech.test/v1/",
        }
    )

    assert settings.base_url == "https://speech.test/v1"
    assert LONG_LIVED_KEY not in repr(settings)


def test_token_request_uses_long_lived_key_only_in_provider_authorization() -> None:
    captured: dict[str, str] = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={"access_token": "temporary-jwt", "expires_in": 30},
            request=request,
        )

    token = asyncio.run(_service(handle_request).issue_temporary_token())

    assert captured == {
        "url": "https://api.deepgram.com/v1/auth/grant",
        "authorization": f"Token {LONG_LIVED_KEY}",
    }
    assert token == DeepgramTemporaryToken(
        access_token="temporary-jwt",
        expires_in=30,
    )
    assert LONG_LIVED_KEY not in repr(token)


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (401, "rejected the configured credentials"),
        (403, "rejected the configured credentials"),
        (429, "temporarily rate limited"),
        (500, "could not start voice input"),
    ],
)
def test_token_request_maps_provider_rejections_without_secret(
    status_code: int,
    message: str,
) -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    with pytest.raises(DeepgramServiceError, match=message) as error_info:
        asyncio.run(_service(handle_request).issue_temporary_token())

    assert LONG_LIVED_KEY not in str(error_info.value)


def test_token_request_maps_timeout_without_secret() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timeout", request=request)

    with pytest.raises(DeepgramServiceError, match="timed out") as error_info:
        asyncio.run(_service(handle_request).issue_temporary_token())

    assert LONG_LIVED_KEY not in str(error_info.value)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"access_token": "", "expires_in": 30},
        {"access_token": "temporary", "expires_in": "30"},
        {"access_token": "temporary", "expires_in": 0},
        {"access_token": "temporary", "expires_in": 3601},
    ],
)
def test_token_request_rejects_malformed_provider_response(
    payload: object,
) -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with pytest.raises(DeepgramServiceError, match="invalid"):
        asyncio.run(_service(handle_request).issue_temporary_token())


def test_token_endpoint_returns_only_temporary_credential() -> None:
    class StubDeepgramService:
        async def issue_temporary_token(self) -> DeepgramTemporaryToken:
            return DeepgramTemporaryToken(
                access_token="temporary-browser-token",
                expires_in=30,
            )

    app.dependency_overrides[get_deepgram_service] = StubDeepgramService
    try:
        response = TestClient(app).post("/voice/deepgram/token")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "temporary-browser-token",
        "expires_in": 30,
    }
    assert LONG_LIVED_KEY not in response.text


def test_missing_configuration_offers_typed_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)

    response = TestClient(app).post("/voice/deepgram/token")

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
    assert "typing" in response.json()["detail"]
    assert "DEEPGRAM_API_KEY" not in response.text


def test_frontend_source_cannot_reference_server_side_key() -> None:
    frontend = Path(__file__).parents[2] / "frontend"
    source_files = [
        *frontend.joinpath("src").rglob("*.ts"),
        *frontend.joinpath("src").rglob("*.tsx"),
        *frontend.joinpath("scripts").rglob("*.mjs"),
    ]

    assert source_files
    for source_file in source_files:
        source = source_file.read_text(encoding="utf-8")
        assert "DEEPGRAM_API_KEY" not in source
        assert LONG_LIVED_KEY not in source


def _service(handler: object) -> DeepgramService:
    return DeepgramService(
        DeepgramSettings(api_key=LONG_LIVED_KEY),
        transport=httpx.MockTransport(handler),
    )
