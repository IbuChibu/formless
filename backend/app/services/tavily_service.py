from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from typing import Mapping, Optional

import httpx


DEFAULT_TAVILY_BASE_URL = "https://api.tavily.com"
DEFAULT_TIMEOUT_SECONDS = 12.0
MAX_TAVILY_RESULTS = 5


class TavilyConfigurationError(RuntimeError):
    """Raised when live web guidance has not been configured."""


class TavilyServiceError(RuntimeError):
    """Raised when Tavily cannot return a usable search response."""


@dataclass(frozen=True)
class TavilySettings:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_TAVILY_BASE_URL

    @classmethod
    def from_environment(
        cls,
        environment: Optional[Mapping[str, str]] = None,
    ) -> TavilySettings:
        values = os.environ if environment is None else environment
        api_key = values.get("TAVILY_API_KEY", "").strip()
        if not api_key:
            raise TavilyConfigurationError(
                "Live web guidance is not configured"
            )

        base_url = values.get(
            "TAVILY_BASE_URL",
            DEFAULT_TAVILY_BASE_URL,
        ).strip()
        if not base_url:
            raise TavilyConfigurationError(
                "Live web guidance is not configured"
            )
        return cls(api_key=api_key, base_url=base_url.rstrip("/"))


@dataclass(frozen=True)
class TavilySearchResult:
    title: str
    url: str
    content: str
    score: float


class TavilyService:
    def __init__(
        self,
        settings: Optional[TavilySettings],
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    @classmethod
    def from_environment(cls) -> TavilyService:
        return cls(TavilySettings.from_environment())

    @classmethod
    def from_optional_environment(cls) -> TavilyService:
        try:
            settings = TavilySettings.from_environment()
        except TavilyConfigurationError:
            settings = None
        return cls(settings)

    @property
    def configured(self) -> bool:
        return self._settings is not None

    async def search(
        self,
        query: str,
        *,
        max_results: int = MAX_TAVILY_RESULTS,
    ) -> tuple[TavilySearchResult, ...]:
        if self._settings is None:
            raise TavilyConfigurationError(
                "Live web guidance is not configured"
            )
        normalized_query = " ".join(query.split())
        if not normalized_query or len(normalized_query) > 500:
            raise ValueError("Tavily search query is invalid")
        if not 1 <= max_results <= MAX_TAVILY_RESULTS:
            raise ValueError("Tavily result limit is invalid")

        payload = {
            "query": normalized_query,
            "search_depth": "basic",
            "chunks_per_source": 1,
            "max_results": max_results,
            "topic": "general",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_image_descriptions": False,
            "include_favicon": False,
            "auto_parameters": False,
            "safe_search": True,
        }

        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT_SECONDS,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._settings.base_url}/search",
                    headers={
                        "Authorization": f"Bearer {self._settings.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise TavilyServiceError(
                "Live web guidance search timed out"
            ) from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            if status_code in {401, 403}:
                message = "Tavily rejected the configured credentials"
            elif status_code == 429:
                message = "Tavily is temporarily rate limited"
            elif status_code in {432, 433}:
                message = "Tavily usage limit has been reached"
            else:
                message = "Tavily could not complete the guidance search"
            raise TavilyServiceError(message) from error
        except httpx.RequestError as error:
            raise TavilyServiceError(
                "Tavily is unavailable"
            ) from error

        try:
            response_data = response.json()
            raw_results = response_data["results"]
            if not isinstance(raw_results, list):
                raise TypeError("results must be a list")
            results = tuple(
                _parse_result(result)
                for result in raw_results[:MAX_TAVILY_RESULTS]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise TavilyServiceError(
                "Tavily returned an invalid response"
            ) from error
        return results


def _parse_result(result: object) -> TavilySearchResult:
    if not isinstance(result, dict):
        raise TypeError("Tavily result must be an object")
    title = result.get("title")
    url = result.get("url")
    content = result.get("content")
    score = result.get("score", 0.0)
    if (
        not isinstance(title, str)
        or not isinstance(url, str)
        or not isinstance(content, str)
        or not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not math.isfinite(float(score))
    ):
        raise TypeError("Tavily result has invalid fields")
    return TavilySearchResult(
        title=title,
        url=url,
        content=content,
        score=float(score),
    )
