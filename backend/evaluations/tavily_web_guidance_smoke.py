from __future__ import annotations

import asyncio
import json

from app.services.form_agent import FormAgentRequest
from app.services.form_agent.web_guidance import (
    plan_web_guidance_lookup,
    prepare_web_guidance,
)
from app.services.tavily_service import TavilyService


async def run_smoke_test() -> None:
    request = FormAgentRequest.model_validate(
        {
            "form_context": {
                "title": "Community support application",
                "instructions": [],
            },
            "fields": [
                {
                    "id": "family_name",
                    "label": "Family name",
                    "question": "What is your family name?",
                    "type": "text",
                    "status": "unanswered",
                }
            ],
            "conversation_state": {
                "phase": "awaiting_answer",
                "active_field_id": "family_name",
                "pending_proposal": None,
            },
            "event": {
                "type": "message",
                "content": "What does family name mean on this form?",
            },
            "history": [],
        }
    )
    lookup = plan_web_guidance_lookup(request, ())
    if lookup is None:
        raise RuntimeError("The smoke-test request did not qualify for lookup")

    service = TavilyService.from_environment()
    results = await service.search(lookup.query)
    guidance = prepare_web_guidance(request, lookup, results)
    print(
        json.dumps(
            {
                "provider": guidance.provider,
                "status": guidance.status,
                "source_count": len(guidance.sources),
                "sources": [
                    {"title": source.title, "url": source.url}
                    for source in guidance.sources
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
