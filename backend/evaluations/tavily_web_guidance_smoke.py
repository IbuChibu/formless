from __future__ import annotations

import asyncio
import json

from app.services.form_agent import FormAgentRequest
from app.services.form_agent.web_guidance import (
    filter_relevant_web_results,
    plan_web_guidance_lookup,
    prepare_web_guidance,
)
from app.services.tavily_service import TavilyService


async def run_smoke_test() -> None:
    request = FormAgentRequest.model_validate(
        {
            "form_context": {
                "title": "Form W-9",
                "instructions": [],
            },
            "fields": [
                {
                    "id": "w9_line_1",
                    "label": "Name of entity or individual",
                    "question": (
                        "Name of entity/individual. For a sole proprietor or "
                        "disregarded entity, enter the owner's name on line 1."
                    ),
                    "type": "text",
                    "status": "unanswered",
                }
            ],
            "conversation_state": {
                "phase": "awaiting_answer",
                "active_field_id": "w9_line_1",
                "pending_proposal": None,
            },
            "event": {
                "type": "message",
                "content": "What name should I enter on Form W-9 line 1?",
            },
            "history": [],
        }
    )
    lookup = plan_web_guidance_lookup(request, ())
    if lookup is None:
        raise RuntimeError("The smoke-test request did not qualify for lookup")

    service = TavilyService.from_environment()
    results = await service.search(lookup.query)
    relevant_results = filter_relevant_web_results(
        request,
        lookup,
        results,
    )
    guidance = prepare_web_guidance(request, lookup, results)
    print(
        json.dumps(
            {
                "provider": guidance.provider,
                "status": guidance.status,
                "returned_result_count": len(results),
                "relevant_result_count": len(relevant_results),
                "selected_source_count": len(guidance.sources),
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
