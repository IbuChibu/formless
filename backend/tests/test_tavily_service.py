from __future__ import annotations

import asyncio
import json
from typing import Callable

import httpx
import pytest

from app.services.tavily_service import (
    TavilyConfigurationError,
    TavilyService,
    TavilyServiceError,
    TavilySettings,
)


def test_tavily_settings_are_server_side_and_secret_is_hidden() -> None:
    settings = TavilySettings.from_environment(
        {
            "TAVILY_API_KEY": "test-secret",
            "TAVILY_BASE_URL": "https://search.test/",
        }
    )

    assert settings.base_url == "https://search.test"
    assert "test-secret" not in repr(settings)


def test_tavily_settings_require_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(TavilyConfigurationError, match="not configured"):
        TavilySettings.from_environment({})

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    service = TavilyService.from_optional_environment()
    assert service.configured is False


def test_tavily_search_uses_bounded_snippet_only_payload() -> None:
    captured: dict[str, object] = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "answer": "This provider answer must be ignored.",
                "results": [
                    {
                        "title": "Official instructions",
                        "url": "https://agency.gov/form/help",
                        "content": "A bounded search snippet.",
                        "score": 0.91,
                        "raw_content": "Raw page content must be ignored.",
                    }
                ],
            },
        )

    service = TavilyService(
        TavilySettings(
            api_key="test-secret",
            base_url="https://search.test",
        ),
        transport=httpx.MockTransport(handle_request),
    )

    results = asyncio.run(service.search("Official form instructions"))

    assert captured["url"] == "https://search.test/search"
    assert captured["authorization"] == "Bearer test-secret"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload == {
        "query": "Official form instructions",
        "search_depth": "basic",
        "chunks_per_source": 1,
        "max_results": 5,
        "topic": "general",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "include_favicon": False,
        "auto_parameters": False,
        "safe_search": True,
    }
    assert len(results) == 1
    assert results[0].content == "A bounded search snippet."
    assert not hasattr(results[0], "raw_content")


@pytest.mark.parametrize(
    ("status_code", "expected_message"),
    [
        (401, "rejected the configured credentials"),
        (429, "temporarily rate limited"),
        (432, "usage limit"),
        (500, "could not complete"),
    ],
)
def test_tavily_search_maps_provider_status_errors(
    status_code: int,
    expected_message: str,
) -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    service = _service(handle_request)

    with pytest.raises(TavilyServiceError, match=expected_message):
        asyncio.run(service.search("form instructions"))


def test_tavily_search_maps_timeout() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(TavilyServiceError, match="timed out"):
        asyncio.run(_service(handle_request).search("form instructions"))


@pytest.mark.parametrize(
    "response_data",
    [
        {},
        {"results": "not-a-list"},
        {"results": [{"title": "Missing fields"}]},
        {
            "results": [
                {
                    "title": "Result",
                    "url": "https://example.com",
                    "content": "Snippet",
                    "score": "high",
                }
            ]
        },
    ],
)
def test_tavily_search_rejects_invalid_provider_responses(
    response_data: object,
) -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_data, request=request)

    with pytest.raises(TavilyServiceError, match="invalid response"):
        asyncio.run(_service(handle_request).search("form instructions"))


def test_tavily_search_accepts_an_empty_result_list() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []}, request=request)

    assert asyncio.run(_service(handle_request).search("form instructions")) == ()


def _service(
    handler: Callable[[httpx.Request], httpx.Response],
) -> TavilyService:
    return TavilyService(
        TavilySettings(api_key="test-secret"),
        transport=httpx.MockTransport(handler),
    )
