from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Mapping, Optional

import httpx


DEFAULT_DEEPGRAM_BASE_URL = "https://api.deepgram.com/v1"
DEFAULT_TIMEOUT_SECONDS = 10.0


class DeepgramConfigurationError(RuntimeError):
    """Raised when Deepgram speech recognition is not configured."""


class DeepgramServiceError(RuntimeError):
    """Raised when Deepgram cannot issue a temporary browser credential."""


@dataclass(frozen=True)
class DeepgramSettings:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_DEEPGRAM_BASE_URL

    @classmethod
    def from_environment(
        cls,
        environment: Optional[Mapping[str, str]] = None,
    ) -> DeepgramSettings:
        values = os.environ if environment is None else environment
        api_key = values.get("DEEPGRAM_API_KEY", "").strip()
        base_url = values.get(
            "DEEPGRAM_BASE_URL",
            DEFAULT_DEEPGRAM_BASE_URL,
        ).strip()
        if not api_key or not base_url:
            raise DeepgramConfigurationError(
                "Deepgram voice input is not configured"
            )
        return cls(api_key=api_key, base_url=base_url.rstrip("/"))


@dataclass(frozen=True)
class DeepgramTemporaryToken:
    access_token: str = field(repr=False)
    expires_in: int


class DeepgramService:
    def __init__(
        self,
        settings: DeepgramSettings,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    @classmethod
    def from_environment(cls) -> DeepgramService:
        return cls(DeepgramSettings.from_environment())

    async def issue_temporary_token(self) -> DeepgramTemporaryToken:
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT_SECONDS,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._settings.base_url}/auth/grant",
                    headers={
                        "Authorization": f"Token {self._settings.api_key}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise DeepgramServiceError(
                "Deepgram temporary credentials timed out"
            ) from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                message = "Deepgram rejected the configured credentials"
            elif error.response.status_code == 429:
                message = "Deepgram is temporarily rate limited"
            else:
                message = "Deepgram could not start voice input"
            raise DeepgramServiceError(message) from error
        except httpx.RequestError as error:
            raise DeepgramServiceError(
                "Deepgram voice input is unavailable"
            ) from error

        try:
            data = response.json()
            access_token = data["access_token"]
            expires_in = data["expires_in"]
        except (KeyError, TypeError, ValueError) as error:
            raise DeepgramServiceError(
                "Deepgram returned an invalid temporary credential"
            ) from error

        if (
            not isinstance(access_token, str)
            or not access_token.strip()
            or not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or not 1 <= expires_in <= 3600
        ):
            raise DeepgramServiceError(
                "Deepgram returned an invalid temporary credential"
            )

        return DeepgramTemporaryToken(
            access_token=access_token.strip(),
            expires_in=expires_in,
        )
