"""Deterministic, bounded policy for the optional support introduction."""

from __future__ import annotations

import re
from typing import Optional

from .models import (
    AdvanceEvent,
    AssistanceNeed,
    AssistancePreferences,
    AssistancePreferencesUpdatedAction,
    ConversationAction,
    FormAgentAction,
    FormAgentRequest,
    InteractionModePreference,
    MessageEvent,
    field_question,
    request_active_field_id,
    truncate_text,
)
from .navigation_policy import build_next_field_question


_NEED_ORDER: tuple[AssistanceNeed, ...] = (
    "plain_language",
    "slower_pace",
    "organise_details",
    "reassurance",
    "explain_bureaucracy",
    "other",
)

_NEED_PATTERNS: dict[AssistanceNeed, tuple[re.Pattern[str], ...]] = {
    "plain_language": (
        re.compile(
            r"\b(?:plain|simple|simpler|easy|easier)\s+"
            r"(?:language|words?|wording|english)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:wording|words?|language)\s+(?:is|are|feels?|seems?)\s+"
            r"(?:confusing|difficult|hard)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:do\s+not|don't|cannot|can't)\s+understand\s+"
            r"(?:the\s+)?(?:words?|wording|language)\b",
            re.IGNORECASE,
        ),
    ),
    "slower_pace": (
        re.compile(
            r"\b(?:go|take\s+it|work)\s+(?:more\s+)?slow(?:ly)?\b|"
            r"\bslow\s+down\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:one|a)\s+(?:question|thing|step)\s+at\s+a\s+time\b|"
            r"\bstep\s+by\s+step\b|\bdo\s+not\s+rush\b|\bdon't\s+rush\b",
            re.IGNORECASE,
        ),
    ),
    "organise_details": (
        re.compile(
            r"\b(?:help\s+(?:me\s+)?(?:organise|organize|sort)|"
            r"organise|organize)\s+(?:my\s+)?(?:details|information|answers?)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:which|what|right)\s+(?:box|field|place)\b|"
            r"\bwhere\s+(?:my\s+)?(?:details|information|answers?)\s+(?:go|belong)\b",
            re.IGNORECASE,
        ),
    ),
    "reassurance": (
        re.compile(
            r"\b(?:worried|nervous|stressed|anxious)\b.*\b(?:mistakes?|wrong|form)\b|"
            r"\b(?:mistakes?|wrong)\b.*\b(?:worried|nervous|stressed|anxious)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:reassure|check\s+with\s+me|make\s+(?:the\s+)?review\s+clear|"
            r"tell\s+me\s+before\s+(?:you|anything))\b",
            re.IGNORECASE,
        ),
    ),
    "explain_bureaucracy": (
        re.compile(
            r"\b(?:official|formal|legal|government|bureaucratic|form)\s+"
            r"(?:language|wording|words?|jargon)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:bureaucracy|bureaucratic|official\s+jargon)\b",
            re.IGNORECASE,
        ),
    ),
    "other": (),
}

_SKIP_SETUP_PATTERN = re.compile(
    r"^(?:please\s+)?(?:just\s+)?(?:start|begin|continue)(?:\s+(?:the\s+)?form)?"
    r"[.!]?$|^(?:skip|skip\s+this|no\s+special\s+help|standard\s+(?:is\s+)?fine)"
    r"[.!]?$",
    re.IGNORECASE,
)
_RESET_PREFERENCES_PATTERN = re.compile(
    r"\b(?:go\s+back\s+to|use|return\s+to)\s+(?:the\s+)?"
    r"(?:standard|default)\s+(?:help|settings?)\b",
    re.IGNORECASE,
)
_MID_FORM_PREFERENCE_PATTERN = re.compile(
    r"\b(?:please\s+slow\s+down|please\s+go\s+slower|"
    r"from\s+now\s+on|for\s+the\s+rest\s+of\s+the\s+form|"
    r"i(?:'d|\s+would)\s+rather\s+(?:speak|talk|type)|"
    r"i\s+prefer\s+(?:speaking|talking|typing))\b",
    re.IGNORECASE,
)


def assistance_preference_action(
    request: FormAgentRequest,
) -> Optional[FormAgentAction]:
    """Return a closed support action without interpreting form facts."""
    if request.conversation_state.phase == "support_setup":
        if not isinstance(request.event, (AdvanceEvent, MessageEvent)):
            return None
        return _support_setup_action(request)

    if not isinstance(request.event, MessageEvent):
        return None

    message = request.event.content.strip()
    if _RESET_PREFERENCES_PATTERN.search(message):
        return _mid_form_update(request, AssistancePreferences())
    if _MID_FORM_PREFERENCE_PATTERN.search(message) is None:
        return None

    needs = _matched_needs(message)
    interaction_found, interaction_mode = _interaction_preference(message)
    if not needs and not interaction_found:
        return None

    preferences = _merged_preferences(
        request.assistance_preferences,
        needs,
        interaction_mode if interaction_found else None,
    )
    return _mid_form_update(request, preferences)


def _support_setup_action(request: FormAgentRequest) -> FormAgentAction:
    event = request.event
    preferences = request.assistance_preferences
    step = request.conversation_state.support_setup_step or "needs"

    if isinstance(event, AdvanceEvent):
        if _has_explicit_preferences(preferences):
            return _complete_setup(request, preferences, skipped=False)
        return ConversationAction(
            action="conversation",
            message=(
                "Before we begin, what tends to make forms difficult for you? "
                "I can use simpler words, go one question at a time, explain "
                "official wording, help organise details, or make review points "
                "clearer. Tell me what would help, or say “just start”."
            ),
            field_id=None,
        )

    if not isinstance(event, MessageEvent):
        return ConversationAction(
            action="conversation",
            message="Tell me what would make this form easier, or say “just start”.",
            field_id=None,
        )

    message = event.content.strip()
    if _SKIP_SETUP_PATTERN.fullmatch(message):
        return _complete_setup(
            request,
            preferences,
            skipped=not _has_explicit_preferences(preferences),
        )

    needs = _matched_needs(message)
    interaction_found, interaction_mode = _interaction_preference(message)
    updated = _merged_preferences(
        preferences,
        needs,
        interaction_mode if interaction_found else None,
    )

    if step in {"needs", "needs_after_interaction"}:
        if needs and (
            interaction_found or step == "needs_after_interaction"
        ):
            return _complete_setup(request, updated, skipped=False)
        if needs:
            return AssistancePreferencesUpdatedAction(
                action="assistance_preferences_updated",
                message=(
                    f"{_preference_acknowledgement(updated)} Would you rather "
                    "speak, type, or use either? Choosing voice will not turn "
                    "on your microphone by itself."
                ),
                preferences=updated,
                introduction_status="pending",
                support_setup_step="interaction",
                field_id=None,
            )
        if interaction_found:
            return AssistancePreferencesUpdatedAction(
                action="assistance_preferences_updated",
                message=(
                    "Thanks — I’ve noted how you would rather answer. What "
                    "would make the form itself easier: simpler wording, a "
                    "slower pace, help organising details, clearer review "
                    "points, or explanations of official wording? You can "
                    "also say “just start”."
                ),
                preferences=updated,
                introduction_status="pending",
                support_setup_step="needs_after_interaction",
                field_id=None,
            )
        return ConversationAction(
            action="conversation",
            message=(
                "Thanks for telling me. I won’t make assumptions about what "
                "you need. Would simpler wording, one question at a time, "
                "help organising details, clearer review points, or help with "
                "official wording be useful? You can choose more than one or "
                "say “just start”."
            ),
            field_id=None,
        )

    if interaction_found:
        return _complete_setup(request, updated, skipped=False)
    if needs:
        return AssistancePreferencesUpdatedAction(
            action="assistance_preferences_updated",
            message=(
                f"{_preference_acknowledgement(updated)} Would you rather "
                "speak, type, or use either?"
            ),
            preferences=updated,
            introduction_status="pending",
            support_setup_step="interaction",
            field_id=None,
        )
    return ConversationAction(
        action="conversation",
        message=(
            "Would you rather speak, type, or use either? You can also say "
            "“just start”."
        ),
        field_id=None,
    )


def _complete_setup(
    request: FormAgentRequest,
    preferences: AssistancePreferences,
    *,
    skipped: bool,
) -> AssistancePreferencesUpdatedAction:
    next_field = next(
        (field for field in request.fields if field.status == "unanswered"),
        None,
    )
    if next_field is None:
        return AssistancePreferencesUpdatedAction(
            action="assistance_preferences_updated",
            message="All supported fields have already been reviewed.",
            preferences=preferences,
            introduction_status="skipped" if skipped else "saved",
            field_id=None,
        )

    acknowledgement = (
        "Of course — we’ll use standard guided help."
        if skipped
        else _preference_acknowledgement(preferences)
    )
    return AssistancePreferencesUpdatedAction(
        action="assistance_preferences_updated",
        message=(
            f"{acknowledgement} You can change this later under “Adjust how "
            f"I help”. Let’s begin. {build_next_field_question(next_field)}"
        ),
        preferences=preferences,
        introduction_status="skipped" if skipped else "saved",
        field_id=next_field.id,
    )


def _mid_form_update(
    request: FormAgentRequest,
    preferences: AssistancePreferences,
) -> AssistancePreferencesUpdatedAction:
    active_field_id = request_active_field_id(request)
    return AssistancePreferencesUpdatedAction(
        action="assistance_preferences_updated",
        message=(
            f"{_preference_acknowledgement(preferences)} "
            f"{_current_turn_reminder(request)}"
        ),
        preferences=preferences,
        introduction_status="saved",
        field_id=active_field_id,
    )


def _current_turn_reminder(request: FormAgentRequest) -> str:
    active_field_id = request_active_field_id(request)
    active_field = next(
        (field for field in request.fields if field.id == active_field_id),
        None,
    )
    if active_field is None:
        return "Your form answers have not changed."
    question = truncate_text(field_question(active_field), 180).rstrip(" .?")
    if request.conversation_state.pending_proposal is not None:
        return (
            f'The proposal for “{question}” is still waiting for your review; '
            "nothing has been added or replaced."
        )
    return f'We’re still on “{question}”; your form answer has not changed.'


def _matched_needs(message: str) -> list[AssistanceNeed]:
    return [
        need
        for need in _NEED_ORDER
        if any(pattern.search(message) for pattern in _NEED_PATTERNS[need])
    ]


def _interaction_preference(
    message: str,
) -> tuple[bool, InteractionModePreference]:
    normalized = " ".join(message.casefold().split())
    if re.search(
        r"\b(?:rather|prefer|want|like)\s+(?:to\s+)?(?:speak|talk)|"
        r"\b(?:use\s+)?voice\b|^(?:speak|voice)$",
        normalized,
    ):
        return True, "voice"
    if re.search(
        r"\b(?:rather|prefer|want|like)\s+(?:to\s+)?(?:type|text)|"
        r"\btyping\b|^(?:type|typing)$",
        normalized,
    ):
        return True, "typing"
    if re.search(
        r"\b(?:either|no\s+preference|do\s+not\s+mind|don't\s+mind|"
        r"whichever)\b",
        normalized,
    ):
        return True, "no_preference"
    return False, "no_preference"


def _merged_preferences(
    current: AssistancePreferences,
    needs: list[AssistanceNeed],
    interaction_mode: Optional[InteractionModePreference],
) -> AssistancePreferences:
    selected = set(current.support_needs)
    selected.update(needs)
    ordered = [need for need in _NEED_ORDER if need in selected]
    return AssistancePreferences(
        support_needs=ordered,
        interaction_mode=interaction_mode or current.interaction_mode,
        other_note=current.other_note,
        assistance_language=current.assistance_language,
    )


def _has_explicit_preferences(preferences: AssistancePreferences) -> bool:
    return bool(
        preferences.support_needs
        or preferences.interaction_mode != "no_preference"
        or preferences.other_note
    )


def _preference_acknowledgement(
    preferences: AssistancePreferences,
) -> str:
    labels = {
        "plain_language": "use simpler wording",
        "slower_pace": "take one thing at a time",
        "organise_details": "help organise the details you provide",
        "reassurance": "make every review point clear",
        "explain_bureaucracy": "explain unfamiliar official wording",
        "other": "follow your saved communication note",
    }
    selected = [labels[need] for need in preferences.support_needs]
    if preferences.interaction_mode == "voice":
        selected.append("make speaking the prominent option")
    elif preferences.interaction_mode == "typing":
        selected.append("make typing the prominent option")

    if not selected:
        return "Got it — I’ll use standard guided help."
    if len(selected) == 1:
        summary = selected[0]
    else:
        summary = ", ".join(selected[:-1]) + f", and {selected[-1]}"
    return f"Thanks — I’ll {summary}."
