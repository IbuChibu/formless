from __future__ import annotations

from difflib import SequenceMatcher
import re

from .models import (
    ConversationScenario,
    RecordedTurn,
    ScenarioScores,
)


_INTERNAL_JARGON = (
    "field_id",
    "conversation_state",
    "pending_proposal",
    '"effect"',
    "json",
)
_EMPATHY_TERMS = (
    "understand",
    "frustrat",
    "sorry",
    "we can",
    "let's",
    "one step",
    "plain",
)
_HELPFUL_CLARIFICATION_TERMS = (
    "for example",
    "in other words",
    "it means",
    "asks for",
    "is asking",
    "you can",
    "tell me",
    "which part",
    "when did",
    "what date",
)
_READ_BACK_REQUEST = re.compile(
    r"\b(?:repeat|say\s+(?:that|it)\s+again|read\s+(?:that|it)\s+back|"
    r"what\s+did\s+you\s+hear)\b",
    re.IGNORECASE,
)


def score_scenario(
    scenario: ConversationScenario,
    transcript: list[RecordedTurn],
    actual_state: dict[str, dict[str, object]],
) -> tuple[ScenarioScores, list[str]]:
    failures = [
        f"turn {turn.index} ({turn.id}): {failure}"
        for turn in transcript
        for failure in turn.expectation_failures + turn.behavior_failures
    ]
    failures.extend(_implicit_review_failures(transcript))
    expected_turn_count = len(scenario.turns)
    if len(transcript) != expected_turn_count:
        failures.append(
            f"conversation stopped after {len(transcript)} of "
            f"{expected_turn_count} scheduled turns"
        )
    failures.extend(
        f"turn {turn.index} ({turn.id}): {turn.error}"
        for turn in transcript
        if turn.error is not None
    )

    state_checks = 0
    state_matches = 0
    expected = scenario.expected_final
    for field_id, value in expected.confirmed_values.items():
        state_checks += 1
        actual = actual_state[field_id]
        if actual["status"] == "confirmed" and actual["confirmed_value"] == value:
            state_matches += 1
        else:
            failures.append(
                f"final field {field_id!r}: expected confirmed value {value!r}, "
                f"got {actual}"
            )
    for field_id in expected.skipped_field_ids:
        state_checks += 1
        actual = actual_state[field_id]
        if actual["status"] == "skipped":
            state_matches += 1
        else:
            failures.append(
                f"final field {field_id!r}: expected skipped, got {actual}"
            )
    for field_id in expected.unanswered_field_ids:
        state_checks += 1
        actual = actual_state[field_id]
        if actual["status"] == "unanswered":
            state_matches += 1
        else:
            failures.append(
                f"final field {field_id!r}: expected unanswered, got {actual}"
            )
    form_state_accuracy = _rate(state_matches, state_checks)

    invention_failures = 0
    for turn in transcript:
        effect = turn.response_effect or {}
        if effect.get("effect") in {"proposal", "replacement_proposal"}:
            field_id = effect.get("field_id")
            value = effect.get("prepared_value")
            allowed = scenario.allowed_proposals.get(str(field_id), [])
            if value not in allowed and not _grounded_in_user_messages(
                value,
                transcript,
                turn.index,
            ):
                invention_failures += 1
                failure = (
                    f"turn {turn.index} ({turn.id}): proposal {value!r} for "
                    f"{field_id!r} was not grounded in user-supplied information"
                )
                if failure not in failures:
                    failures.append(failure)

        assistant_message = (turn.assistant_message or "").casefold()
        for term in scenario.forbidden_assistant_terms:
            if term.casefold() not in assistant_message:
                continue
            invention_failures += 1
            failure = (
                f"turn {turn.index} ({turn.id}): assistant introduced the "
                f"unsupported claim {term!r}"
            )
            if failure not in failures:
                failures.append(failure)

    context_turns = [turn for turn in transcript if "context_retention" in turn.tags]
    context_successes = sum(
        not turn.expectation_failures and turn.error is None for turn in context_turns
    )
    context_score = (
        _rate(context_successes, len(context_turns)) if context_turns else None
    )

    repeated_pairs = 0
    comparable_pairs = 0
    previous_message: str | None = None
    for turn in transcript:
        current = turn.assistant_message
        if current is None:
            continue
        if previous_message is not None:
            comparable_pairs += 1
            repeated_pairs += int(_near_duplicate(previous_message, current))
        previous_message = current
    repetition_rate = _rate(repeated_pairs, comparable_pairs)

    clarification_turns = [
        turn for turn in transcript if "clarification" in turn.tags
    ]
    clarification_scores = [
        _clarification_score(turn, transcript) for turn in clarification_turns
    ]
    clarification_quality = (
        round(sum(clarification_scores) / len(clarification_scores), 3)
        if clarification_scores
        else None
    )

    recovery_turns = [turn for turn in transcript if "recovery" in turn.tags]
    recovery_success = None
    if "recovery" in scenario.tags or recovery_turns:
        recovery_success = float(
            form_state_accuracy == 1.0
            and all(turn.error is None for turn in transcript)
            and all(not turn.expectation_failures for turn in recovery_turns)
        )

    latest_answer_turns = [
        turn for turn in transcript if "latest_answer" in turn.tags
    ]
    latest_answer_adherence = (
        _rate(
            sum(
                not turn.expectation_failures and turn.error is None
                for turn in latest_answer_turns
            ),
            len(latest_answer_turns),
        )
        if latest_answer_turns
        else None
    )
    contradiction_failures = sum(
        1
        for turn in transcript
        if "contradiction_check" in turn.tags
        for failure in turn.expectation_failures
        if failure.startswith("assistant message included forbidden terms:")
    )

    volunteered_fact_recall = _tagged_success_rate(
        transcript,
        "volunteered_fact_recall",
    )
    side_question_recovery = _tagged_success_rate(
        transcript,
        "side_question_recovery",
    )
    interruption_recovery = _tagged_success_rate(
        transcript,
        "interruption_recovery",
    )
    clarification_success = _tagged_success_rate(
        transcript,
        "clarification_success",
    )
    acknowledgement_rate = _behavior_result_rate(
        transcript,
        "acknowledges_user_input",
    )
    speech_suitability = _behavior_result_rate(transcript, "speech_suitable")
    redundant_question_success = _behavior_result_rate(
        transcript,
        "avoids_reasking_known_information",
    )
    redundant_question_rate = (
        round(1.0 - redundant_question_success, 3)
        if redundant_question_success is not None
        else None
    )
    unnecessary_push_success = _behavior_result_rate(
        transcript,
        "avoids_unnecessary_advance",
    )
    unnecessary_push_rate = (
        round(1.0 - unnecessary_push_success, 3)
        if unnecessary_push_success is not None
        else None
    )
    all_behavior_results = [
        result
        for turn in transcript
        for result in turn.behavior_results.values()
    ]
    human_helper_behavior_rate = (
        _rate(sum(all_behavior_results), len(all_behavior_results))
        if all_behavior_results
        else None
    )
    confirmed_field_count = sum(
        (turn.response_effect or {}).get("effect") == "confirmed"
        for turn in transcript
    )
    turns_per_confirmed_field = (
        round(len(transcript) / confirmed_field_count, 3)
        if confirmed_field_count
        else None
    )
    confirmation_boundary_failures = sum(
        _confirmation_boundary_failures(turn) for turn in transcript
    )

    naturalness_scores = [
        _naturalness_score(turn, transcript)
        for turn in transcript
        if turn.assistant_message is not None
    ]
    heuristic_naturalness = (
        round(sum(naturalness_scores) / len(naturalness_scores), 3)
        if naturalness_scores
        else 1.0
    )

    return (
        ScenarioScores(
            form_state_accuracy=form_state_accuracy,
            context_retention=context_score,
            unnecessary_repetition_rate=repetition_rate,
            clarification_quality=clarification_quality,
            recovery_success=recovery_success,
            heuristic_naturalness=heuristic_naturalness,
            invention_failures=invention_failures,
            latest_answer_adherence=latest_answer_adherence,
            contradiction_failures=contradiction_failures,
            volunteered_fact_recall=volunteered_fact_recall,
            redundant_question_rate=redundant_question_rate,
            side_question_recovery=side_question_recovery,
            unnecessary_push_rate=unnecessary_push_rate,
            speech_suitability=speech_suitability,
            acknowledgement_rate=acknowledgement_rate,
            interruption_recovery=interruption_recovery,
            clarification_success=clarification_success,
            human_helper_behavior_rate=human_helper_behavior_rate,
            confirmed_field_count=confirmed_field_count,
            turns_per_confirmed_field=turns_per_confirmed_field,
            confirmation_boundary_failures=confirmation_boundary_failures,
        ),
        failures,
    )


def _implicit_review_failures(transcript: list[RecordedTurn]) -> list[str]:
    """Apply stable review invariants without changing versioned scenarios."""

    failures: list[str] = []
    for turn in transcript:
        message = turn.visible_user_message or ""
        if _READ_BACK_REQUEST.search(message) is None:
            continue
        if turn.request_state.get("phase") not in {
            "awaiting_confirmation",
            "awaiting_replacement_confirmation",
        }:
            continue
        pending = turn.request_state.get("pending_proposal")
        if not isinstance(pending, dict) or "value" not in pending:
            continue
        value = pending["value"]
        expected = (
            "yes"
            if value is True
            else "no"
            if value is False
            else " ".join(str(value).casefold().split())
        )
        assistant = " ".join(
            (turn.assistant_message or "").casefold().split()
        )
        if expected and expected not in assistant:
            failures.append(
                f"turn {turn.index} ({turn.id}): assistant did not read back "
                "the visibly pending value"
            )
    return failures


def _naturalness_score(
    turn: RecordedTurn,
    transcript: list[RecordedTurn],
) -> float:
    message = turn.assistant_message or ""
    normalized = " ".join(message.casefold().split())
    if turn.error is not None or not message:
        return 1.0
    # Surface-level fluency alone must not receive a perfect score. Untagged,
    # concise, non-repetitive replies top out at 4/5; demonstrated behavioural
    # success is required for a higher score.
    score = 3.0
    word_count = len(message.split())
    if 2 <= word_count <= 60:
        score += 0.5
    if message.count("?") <= 2:
        score += 0.25
    if not any(term in normalized for term in _INTERNAL_JARGON):
        score += 0.25
    if turn.behavior_results:
        behavior_rate = sum(turn.behavior_results.values()) / len(
            turn.behavior_results
        )
        score += behavior_rate
    if word_count > 120:
        score -= 1.0
    if word_count > 200:
        score -= 1.0
    if any(term in normalized for term in _INTERNAL_JARGON):
        score -= 2.0
    previous = _previous_assistant_message(turn, transcript)
    if previous is not None and _near_duplicate(previous, message):
        score -= 1.5
    if "emotion" in turn.tags and not any(
        term in normalized for term in _EMPATHY_TERMS
    ):
        score -= 1.0
    if "contradiction_check" in turn.tags and any(
        failure.startswith("assistant message included forbidden terms:")
        for failure in turn.expectation_failures
    ):
        score -= 2.0
    if "style_check" in turn.tags and any(
        failure.startswith("assistant message used ")
        for failure in turn.expectation_failures
    ):
        score -= 1.0
    return max(1.0, round(score, 3))


def _tagged_success_rate(
    transcript: list[RecordedTurn],
    tag: str,
) -> float | None:
    turns = [turn for turn in transcript if tag in turn.tags]
    if not turns:
        return None
    successes = sum(
        turn.error is None
        and not turn.expectation_failures
        and not turn.behavior_failures
        for turn in turns
    )
    return _rate(successes, len(turns))


def _behavior_result_rate(
    transcript: list[RecordedTurn],
    result_name: str,
) -> float | None:
    results = [
        turn.behavior_results[result_name]
        for turn in transcript
        if result_name in turn.behavior_results
    ]
    return _rate(sum(results), len(results)) if results else None


def _confirmation_boundary_failures(turn: RecordedTurn) -> int:
    effect = turn.response_effect or {}
    event_type = turn.user_event.get("type")
    failures = 0
    if effect.get("effect") == "confirmed" and not _used_closed_confirmation_route(
        turn
    ):
        failures += 1

    changed_to_confirmed = [
        field_id
        for field_id, after in turn.fields_after.items()
        if after.get("status") == "confirmed"
        and turn.fields_before.get(field_id) != after
    ]
    if changed_to_confirmed and effect.get("effect") != "confirmed":
        failures += len(changed_to_confirmed)
    if effect.get("effect") in {"proposal", "replacement_proposal", "none"}:
        if turn.fields_after != turn.fields_before:
            failures += 1
    return failures


def _used_closed_confirmation_route(turn: RecordedTurn) -> bool:
    event_type = turn.user_event.get("type")
    if event_type in {"confirm", "confirm_edit"}:
        return True
    if event_type != "message":
        return False
    if turn.request_state.get("phase") not in {
        "awaiting_confirmation",
        "awaiting_replacement_confirmation",
    }:
        return False
    if not turn.request_state.get("pending_proposal"):
        return False
    return any(
        diagnostic.get("route") == "interpreted_action_accepted"
        and diagnostic.get("intent") == "confirm_proposal"
        for diagnostic in turn.route_diagnostics
    )


def _clarification_score(
    turn: RecordedTurn,
    transcript: list[RecordedTurn],
) -> float:
    message = turn.assistant_message or ""
    normalized = " ".join(message.casefold().split())
    if turn.error is not None or not message:
        return 1.0
    score = 5.0
    effect = turn.response_effect or {}
    if effect.get("effect") != "none":
        score -= 2.0
    previous = _previous_assistant_message(turn, transcript)
    if previous is not None and _near_duplicate(previous, message):
        score -= 2.0
    if not (
        "?" in message
        or any(term in normalized for term in _HELPFUL_CLARIFICATION_TERMS)
    ):
        score -= 1.0
    if len(message.split()) > 120:
        score -= 1.0
    return max(1.0, round(score, 3))


def _previous_assistant_message(
    turn: RecordedTurn,
    transcript: list[RecordedTurn],
) -> str | None:
    previous = [
        candidate.assistant_message
        for candidate in transcript
        if candidate.index < turn.index and candidate.assistant_message is not None
    ]
    return previous[-1] if previous else None


def _near_duplicate(first: str, second: str) -> bool:
    first_words = re.findall(r"[\w']+", first.casefold(), re.UNICODE)
    second_words = re.findall(r"[\w']+", second.casefold(), re.UNICODE)
    if not first_words or not second_words:
        return False
    first_text = " ".join(first_words)
    second_text = " ".join(second_words)
    if first_text == second_text:
        return True
    similarity = SequenceMatcher(None, first_text, second_text).ratio()
    shared = set(first_words) & set(second_words)
    containment = len(shared) / min(len(set(first_words)), len(set(second_words)))
    return similarity >= 0.84 or (similarity >= 0.7 and containment >= 0.9)


def _grounded_in_user_messages(
    value: object,
    transcript: list[RecordedTurn],
    through_turn: int,
) -> bool:
    if not isinstance(value, str):
        return False
    value_tokens = set(re.findall(r"[\w']+", value.casefold(), re.UNICODE))
    if not value_tokens:
        return False
    user_tokens: set[str] = set()
    for turn in transcript:
        if turn.index > through_turn or turn.visible_user_message is None:
            continue
        user_tokens.update(
            re.findall(
                r"[\w']+",
                turn.visible_user_message.casefold(),
                re.UNICODE,
            )
        )
    return value_tokens <= user_tokens


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 1.0
