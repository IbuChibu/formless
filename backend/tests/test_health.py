import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app, get_nemotron_service


client = TestClient(app)


def test_health_returns_api_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "formless-api"}


def test_health_allows_local_frontend_origin() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_missing_nebius_configuration_has_a_specific_recovery_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    with pytest.raises(HTTPException) as error_info:
        get_nemotron_service()

    assert error_info.value.status_code == 503
    assert "Nebius Token Factory is not configured" in str(
        error_info.value.detail
    )
    assert "backend/.env" in str(error_info.value.detail)
    assert "manual PDF editing" in str(error_info.value.detail)
