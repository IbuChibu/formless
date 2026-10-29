from __future__ import annotations

from typing import Optional, Protocol

import httpx

from app.services.form_agent import (
    FormAgentRequest,
    FormAgentResponse,
    FormAgentService,
)
from app.services.form_agent.orchestrator import consume_turn_route_diagnostics


class ConversationTarget(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def respond(self, request: FormAgentRequest) -> FormAgentResponse: ...

    def take_route_diagnostics(self) -> list[dict[str, str]]: ...


class ServiceConversationTarget:
    def __init__(
        self,
        service: FormAgentService,
        *,
        model: str,
        name: str = "in-process FormAgentService",
    ) -> None:
        self._service = service
        self._model = model
        self._name = name
        self._route_diagnostics: list[dict[str, str]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    async def respond(self, request: FormAgentRequest) -> FormAgentResponse:
        try:
            return await self._service.respond(request)
        finally:
            self._route_diagnostics = consume_turn_route_diagnostics()

    def take_route_diagnostics(self) -> list[dict[str, str]]:
        diagnostics = [dict(item) for item in self._route_diagnostics]
        self._route_diagnostics = []
        return diagnostics


class HttpConversationTarget:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 45.0,
        model: str = "server-configured",
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._model = model
        self._transport = transport

    @property
    def name(self) -> str:
        return f"HTTP {self._base_url}/agent/respond"

    @property
    def model(self) -> str:
        return self._model

    async def respond(self, request: FormAgentRequest) -> FormAgentResponse:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.post(
                f"{self._base_url}/agent/respond",
                json=request.model_dump(mode="json"),
            )
        response.raise_for_status()
        return FormAgentResponse.model_validate(response.json())

    def take_route_diagnostics(self) -> list[dict[str, str]]:
        # Remote route details are intentionally absent from the public API.
        return []
