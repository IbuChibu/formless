from __future__ import annotations

from typing import Any

from app.services.form_agent.models import FormAgentRequest, request_active_field_id


def build_conversation_context(request: FormAgentRequest) -> dict[str, Any]:
    """Build bounded, non-PDF conversation context for one Nemotron turn."""
    active_id = request_active_field_id(request)
    active_field = next(
        (field for field in request.fields if field.id == active_id),
        None,
    )
    pending = request.conversation_state.pending_proposal
    fields = [
        {
            "id": field.id,
            "label": field.label,
            "question": field.question or field.label,
            "help_text": field.help_text,
            "section": field.section,
            "page_context": field.page_context,
            "type": field.type,
            "options": field.options or [],
            "status": field.status,
            "confirmed_value": field.confirmed_value,
        }
        for field in request.fields
    ]
    return {
        "form": request.form_context.model_dump(),
        "active_field": (
            next(field for field in fields if field["id"] == active_field.id)
            if active_field is not None
            else None
        ),
        "fields": fields,
        "pending_proposal": pending.model_dump() if pending is not None else None,
        "conversation_phase": request.conversation_state.phase,
        "assistance_preferences": request.assistance_preferences.model_dump(),
        "recent_history": [message.model_dump() for message in request.history],
        "latest_event": request.event.model_dump(),
    }
