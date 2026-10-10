from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import math
import re
from typing import Literal, Optional
from urllib.parse import urlparse, urlunparse

from app.services.tavily_service import TavilySearchResult

from .conversation_policy import message_needs_external_guidance
from .models import (
    FocusFieldEvent,
    ExplainAction,
    FormAgentAction,
    FormAgentError,
    FormAgentRequest,
    MessageEvent,
    OfficialGuidanceCitation,
    ProposeAction,
    WebGuidanceCitation,
    WebGuidanceMetadata,
    field_question,
    request_active_field_id,
    request_message,
    truncate_text,
)
from .official_guidance import GUIDANCE_RESOURCES


WebGuidanceTopic = Literal[
    "meaning",
    "purpose",
    "requirements",
    "where_to_find",
]
WebGuidanceUnavailableReason = Literal[
    "not_configured",
    "provider_failure",
]
EvidenceClaimTopic = Literal[
    "definition",
    "purpose",
    "requiredness",
    "accepted_values",
    "formatting",
    "where_to_find",
]
EvidenceAssessmentStatus = Literal[
    "supported",
    "limited",
    "conflicting",
]

MAX_WEB_QUERY_CHARS = 420
MAX_WEB_RESULTS = 3
MAX_WEB_SNIPPET_CHARS = 500
MAX_WEB_CONTEXT_CHARS = 1200

_PURPOSE_PATTERN = re.compile(
    r"\b(?:why|purpose|reason|used\s+for)\b",
    re.IGNORECASE,
)
_REQUIREMENTS_PATTERN = re.compile(
    r"\b(?:official|instructions?|required?|requirements?|rules?|must|"
    r"allowed?|legal(?:ly)?|eligib(?:le|ility)|mandatory|optional)\b",
    re.IGNORECASE,
)
_WHERE_PATTERN = re.compile(
    r"\b(?:where|find|locate|look\s+up|which\s+document|what\s+document)\b",
    re.IGNORECASE,
)
_MEANING_PATTERN = re.compile(
    r"\b(?:what|which|who|when|how|explain|meaning|mean|help)\b",
    re.IGNORECASE,
)
_PERSONAL_ADVICE_PATTERN = re.compile(
    r"(?:\bwhat\s+should\s+i\s+(?:put|answer|choose|claim)\b|"
    r"\bwhich\s+(?:answer|option)\s+should\s+i\b|"
    r"\b(?:legal|financial|medical|tax)\s+advice\b)",
    re.IGNORECASE,
)
_NEGATIVE_REQUIREMENT_PATTERN = re.compile(
    r"\b(?:not\s+required|isn't\s+required|is\s+optional|optional)\b",
    re.IGNORECASE,
)
_POSITIVE_REQUIREMENT_PATTERN = re.compile(
    r"\b(?:is\s+required|are\s+required|must\s+(?:provide|include|complete)|"
    r"required\s+to)\b",
    re.IGNORECASE,
)
_ACCEPTED_VALUES_PATTERN = re.compile(
    r"\b(?:accepted|allowed|valid)\s+(?:answer|answers|option|options|value|"
    r"values)\b|\bwhich\s+(?:answer|answers|option|options|value|values)\b",
    re.IGNORECASE,
)
_FORMATTING_PATTERN = re.compile(
    r"\b(?:format|formatted|formatting|write|written)\b",
    re.IGNORECASE,
)
_FIELD_LOCATOR_PATTERN = re.compile(
    r"\b(line|box|section|part|item|question)\s*"
    r"(?:no\.?|number)?\s*"
    r"([a-z]?\d+[a-z]?(?:[.-]\d+)?|[ivxlcdm]+)\b",
    re.IGNORECASE,
)
_CLAUSE_SPLIT_PATTERN = re.compile(
    r"(?<=[.!?;])\s+|;\s*|,?\s+(?:but|while|whereas)\s+",
    re.IGNORECASE,
)
_SAFE_QUERY_CHARACTER_PATTERN = re.compile(r"[^\w\s.,()&/:'\-]", re.UNICODE)
_RELEVANCE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_FORM_CODE_PATTERN = re.compile(
    r"\b(?:form[\s_-]*)?([a-z]{1,8})[\s_-]?(\d{1,5}[a-z]?)\b",
    re.IGNORECASE,
)
_VERSION_MARKER_PATTERN = re.compile(
    r"\b(?:version|edition|rev(?:ision)?\.?)\s*[:#-]?\s*"
    r"([0-9][0-9./-]{3,15})",
    re.IGNORECASE,
)
_PUBLIC_AUTHORITY_SUFFIXES = (
    ".gov",
    ".gov.uk",
    ".gc.ca",
    ".gov.au",
)
_FORM_CODE_PREFIX_EXCLUSIONS = frozenset(
    {"box", "chapter", "line", "page", "part", "section"}
)
_GENERIC_FORM_TOKENS = frozenset(
    {
        "application",
        "applications",
        "document",
        "documents",
        "fillable",
        "form",
        "forms",
        "guide",
        "guidance",
        "help",
        "information",
        "instructions",
        "official",
        "online",
        "pdf",
        "request",
        "review",
        "sample",
        "support",
        "worksheet",
    }
)
_GENERIC_FIELD_TOKENS = frozenset(
    {
        "a",
        "about",
        "address",
        "an",
        "and",
        "answer",
        "amount",
        "are",
        "date",
        "details",
        "do",
        "enter",
        "field",
        "for",
        "form",
        "full",
        "here",
        "how",
        "information",
        "is",
        "name",
        "number",
        "of",
        "on",
        "question",
        "requested",
        "should",
        "the",
        "this",
        "to",
        "value",
        "what",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
    }
)
_TOPIC_RELEVANCE_TOKENS: dict[WebGuidanceTopic, frozenset[str]] = {
    "meaning": frozenset(
        {"definition", "defines", "enter", "means", "meaning", "refers", "use"}
    ),
    "purpose": frozenset(
        {"collect", "need", "purpose", "reason", "requested", "used", "why"}
    ),
    "requirements": frozenset(
        {
            "allowed",
            "instructions",
            "must",
            "optional",
            "require",
            "required",
            "requirements",
        }
    ),
    "where_to_find": frozenset(
        {"document", "find", "locate", "obtain", "record", "where"}
    ),
}


@dataclass(frozen=True)
class WebGuidanceLookup:
    topic: WebGuidanceTopic
    query: str


@dataclass(frozen=True)
class _RankedResult:
    citation: WebGuidanceCitation
    score: float
    quality_rank: int
    relevance_rank: int


@dataclass(frozen=True)
class _EvidenceAssessment:
    status: EvidenceAssessmentStatus
    reason: str


def plan_web_guidance_lookup(
    request: FormAgentRequest,
    guidance: tuple[OfficialGuidanceCitation, ...],
) -> Optional[WebGuidanceLookup]:
    if guidance:
        return None
    if not isinstance(request.event, (MessageEvent, FocusFieldEvent)):
        return None

    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        return None
    active_field = next(
        (field for field in request.fields if field.id == active_field_id),
        None,
    )
    if active_field is None or active_field.status != "unanswered":
        return None

    message = request_message(request)
    if _PERSONAL_ADVICE_PATTERN.search(message) is not None:
        return None
    if not message_needs_external_guidance(request):
        return None
    topic = _classify_topic(message)
    if topic is None:
        return None
    return WebGuidanceLookup(
        topic=topic,
        query=build_web_guidance_query(request, topic),
    )


def build_web_guidance_query(
    request: FormAgentRequest,
    topic: WebGuidanceTopic,
) -> str:
    active_field_id = request_active_field_id(request)
    if active_field_id is None:
        raise FormAgentError("Web guidance requires an active field")
    field = next(
        (field for field in request.fields if field.id == active_field_id),
        None,
    )
    if field is None:
        raise FormAgentError("Web guidance requires an active field")

    organization, _ = _known_issuer(request)
    topic_phrase = {
        "meaning": "official instructions meaning",
        "purpose": "official purpose why requested",
        "requirements": "official instructions requirements",
        "where_to_find": "official instructions where to find information",
    }[topic]
    components = [
        _safe_query_part(organization, 100) if organization else "",
        _safe_query_part(request.form_context.title or "fillable PDF form", 120),
        (
            f"form version {_safe_query_part(request.form_context.form_version, 40)}"
            if request.form_context.form_version
            else ""
        ),
        _safe_query_part(field_question(field), 180),
        topic_phrase,
    ]
    query = " ".join(component for component in components if component)
    return truncate_text(query, MAX_WEB_QUERY_CHARS)


def prepare_web_guidance(
    request: FormAgentRequest,
    lookup: WebGuidanceLookup,
    results: tuple[TavilySearchResult, ...],
    *,
    retrieved_at: Optional[datetime] = None,
) -> WebGuidanceMetadata:
    timestamp = (retrieved_at or datetime.now(timezone.utc)).astimezone(
        timezone.utc
    ).replace(microsecond=0)
    retrieved_at_text = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    _, issuer_host = _known_issuer(request)
    ranked_results: list[_RankedResult] = []
    seen_urls: set[str] = set()

    for result in filter_relevant_web_results(request, lookup, results):
        normalized_url = normalize_public_https_url(result.url)
        if normalized_url is None or normalized_url in seen_urls:
            continue
        title = " ".join(result.title.split())
        snippet = " ".join(result.content.split())
        if not title or not snippet:
            continue
        seen_urls.add(normalized_url)
        hostname = urlparse(normalized_url).hostname or ""
        source_quality = _source_quality(hostname, issuer_host)
        quality_rank = {
            "issuing_organization": 3,
            "public_authority": 2,
            "general_web": 1,
        }[source_quality]
        citation = WebGuidanceCitation(
            source_id=(
                "tavily-"
                + hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:16]
            ),
            title=truncate_text(title, 300),
            url=normalized_url,
            hostname=hostname,
            retrieved_at=retrieved_at_text,
            form_version=request.form_context.form_version,
            snippet=truncate_text(snippet, MAX_WEB_SNIPPET_CHARS),
            source_quality=source_quality,
        )
        score = result.score if math.isfinite(result.score) else 0.0
        ranked_results.append(
            _RankedResult(
                citation=citation,
                score=score,
                quality_rank=quality_rank,
                relevance_rank=(
                    _result_relevance_rank(request, lookup, result) or 0
                ),
            )
        )

    ranked_results.sort(
        key=lambda result: (
            result.relevance_rank,
            result.quality_rank,
            result.score,
        ),
        reverse=True,
    )
    selected: list[WebGuidanceCitation] = []
    used_characters = 0
    for ranked in ranked_results:
        if len(selected) >= MAX_WEB_RESULTS:
            break
        snippet_length = len(ranked.citation.snippet)
        if used_characters + snippet_length > MAX_WEB_CONTEXT_CHARS:
            continue
        selected.append(ranked.citation)
        used_characters += snippet_length

    if not selected:
        return WebGuidanceMetadata(
            status="empty",
            topic=lookup.topic,
            notice=(
                "Tavily found no relevant, usable public HTTPS sources for "
                "this field. You can retry without changing any form answer."
            ),
            sources=[],
        )

    lacks_issuer_source = not any(
        source.source_quality == "issuing_organization"
        for source in selected
    )
    assessment = _assess_selected_evidence(
        request,
        lookup,
        selected,
        lacks_issuer_source=lacks_issuer_source,
    )
    return WebGuidanceMetadata(
        status=(
            "used" if assessment.status == "supported" else assessment.status
        ),
        topic=lookup.topic,
        notice=assessment.reason,
        sources=selected,
    )


def unavailable_web_guidance(
    lookup: WebGuidanceLookup,
    reason: WebGuidanceUnavailableReason,
) -> WebGuidanceMetadata:
    notice = {
        "not_configured": (
            "Live web guidance is not configured. You can continue manually "
            "or configure Tavily and retry."
        ),
        "provider_failure": (
            "Tavily could not complete this lookup. You can retry without "
            "changing any form answer or continue manually."
        ),
    }[reason]
    return WebGuidanceMetadata(
        status="unavailable",
        topic=lookup.topic,
        notice=notice,
        sources=[],
    )


def filter_relevant_web_results(
    request: FormAgentRequest,
    lookup: WebGuidanceLookup,
    results: tuple[TavilySearchResult, ...],
) -> tuple[TavilySearchResult, ...]:
    return tuple(
        result
        for result in results
        if _result_relevance_rank(request, lookup, result) is not None
    )


def validate_web_guidance_action(
    action: FormAgentAction,
    guidance: Optional[WebGuidanceMetadata],
) -> None:
    if guidance is None:
        return
    if isinstance(action, ProposeAction):
        raise FormAgentError(
            "Live web guidance cannot supply a personal field value"
        )
    if not isinstance(action, ExplainAction):
        raise FormAgentError(
            "Live web guidance requires an explanation action"
        )


def normalize_public_https_url(value: str) -> Optional[str]:
    try:
        parsed = urlparse(value.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        return None

    normalized_host = hostname.rstrip(".").casefold()
    if (
        "." not in normalized_host
        or normalized_host == "localhost"
        or normalized_host.endswith((".localhost", ".local", ".internal"))
        or not _valid_public_host(normalized_host)
    ):
        return None

    netloc = normalized_host
    path = parsed.path or "/"
    return urlunparse(("https", netloc, path, "", parsed.query, ""))


def _classify_topic(message: str) -> Optional[WebGuidanceTopic]:
    if _PURPOSE_PATTERN.search(message) is not None:
        return "purpose"
    if _REQUIREMENTS_PATTERN.search(message) is not None:
        return "requirements"
    if _WHERE_PATTERN.search(message) is not None:
        return "where_to_find"
    if (
        message.rstrip().endswith("?")
        or _MEANING_PATTERN.search(message) is not None
    ):
        return "meaning"
    return None


def _safe_query_part(value: str, max_length: int) -> str:
    collapsed = " ".join(value.split())
    cleaned = _SAFE_QUERY_CHARACTER_PATTERN.sub(" ", collapsed)
    return truncate_text(" ".join(cleaned.split()), max_length)


def _result_relevance_rank(
    request: FormAgentRequest,
    lookup: WebGuidanceLookup,
    result: TavilySearchResult,
) -> Optional[int]:
    normalized_url = normalize_public_https_url(result.url)
    title = " ".join(result.title.split())
    snippet = " ".join(result.content.split())
    if normalized_url is None or not title or not snippet:
        return None

    result_text = " ".join((normalized_url, title, snippet))
    result_tokens = _relevance_tokens(result_text)
    result_codes = _form_codes(result_text)
    if _has_mismatched_explicit_version(
        request.form_context.form_version,
        result_text,
    ):
        return None

    organization, issuer_host = _known_issuer(request)
    result_host = urlparse(normalized_url).hostname or ""
    issuer_host_match = bool(
        issuer_host
        and (
            result_host == issuer_host
            or result_host.endswith(f".{issuer_host}")
        )
    )
    issuer_text_match = bool(
        organization
        and _strong_token_match(
            _significant_tokens(organization, _GENERIC_FORM_TOKENS),
            result_tokens,
        )
    )

    form_reference_text = " ".join(
        part
        for part in (
            request.form_context.form_id,
            request.form_context.title,
        )
        if part
    )
    expected_codes = _form_codes(form_reference_text)
    code_match = bool(expected_codes & result_codes)
    form_title = request.form_context.title or ""
    form_title_tokens = _significant_tokens(
        form_title,
        _GENERIC_FORM_TOKENS,
    )
    form_token_match = _strong_token_match(
        form_title_tokens,
        result_tokens,
    )
    title_phrase_match = bool(
        len(form_title_tokens) >= 2
        and _normalized_relevance_phrase(form_title)
        in _normalized_relevance_phrase(result_text)
    )
    form_match = code_match or form_token_match or issuer_text_match

    active_field_id = request_active_field_id(request)
    active_field = next(
        (
            field
            for field in request.fields
            if field.id == active_field_id
        ),
        None,
    )
    if active_field is None:
        return None
    field_tokens = _significant_tokens(
        " ".join(
            part
            for part in (
                active_field.label,
                field_question(active_field),
            )
            if part
        ),
        _GENERIC_FIELD_TOKENS,
    )
    field_match = _field_token_match(field_tokens, result_tokens)
    topic_match = bool(
        _TOPIC_RELEVANCE_TOKENS[lookup.topic] & result_tokens
    )

    if issuer_host_match:
        if not (form_match or field_match):
            return None
    elif request.form_context.form_id is not None:
        if not (form_match and field_match):
            return None
    elif not ((code_match or title_phrase_match) and field_match):
        return None

    version_match = _normalized_version(
        request.form_context.form_version
    ) in _explicit_versions(result_text)
    return (
        (4 if issuer_host_match else 0)
        + (4 if code_match else 0)
        + (3 if form_token_match or issuer_text_match else 0)
        + (2 if field_match else 0)
        + (1 if topic_match else 0)
        + (1 if version_match else 0)
    )


def _relevance_tokens(value: str) -> frozenset[str]:
    return frozenset(
        match.group(0).casefold()
        for match in _RELEVANCE_TOKEN_PATTERN.finditer(value)
    )


def _normalized_relevance_phrase(value: str) -> str:
    return " ".join(
        match.group(0).casefold()
        for match in _RELEVANCE_TOKEN_PATTERN.finditer(value)
    )


def _significant_tokens(
    value: str,
    ignored_tokens: frozenset[str],
) -> frozenset[str]:
    return frozenset(
        token
        for token in _relevance_tokens(value)
        if token not in ignored_tokens
        and (len(token) >= 3 or any(character.isdigit() for character in token))
    )


def _strong_token_match(
    expected_tokens: frozenset[str],
    result_tokens: frozenset[str],
) -> bool:
    if len(expected_tokens) < 2:
        return False
    overlap = len(expected_tokens & result_tokens)
    required_overlap = max(2, math.ceil(len(expected_tokens) * 0.5))
    return overlap >= required_overlap


def _field_token_match(
    expected_tokens: frozenset[str],
    result_tokens: frozenset[str],
) -> bool:
    if not expected_tokens:
        return False
    overlap = len(expected_tokens & result_tokens)
    required_overlap = 1 if len(expected_tokens) <= 2 else 2
    return overlap >= required_overlap


def _form_codes(value: str) -> frozenset[str]:
    codes = set()
    for match in _FORM_CODE_PATTERN.finditer(value):
        prefix = match.group(1).casefold()
        if prefix in _FORM_CODE_PREFIX_EXCLUSIONS:
            continue
        codes.add(f"{prefix}{match.group(2).casefold()}")
    return frozenset(codes)


def _explicit_versions(value: str) -> frozenset[str]:
    return frozenset(
        _normalized_version(match.group(1))
        for match in _VERSION_MARKER_PATTERN.finditer(value)
    )


def _normalized_version(value: Optional[str]) -> str:
    if value is None:
        return ""
    return "".join(
        character
        for character in value.casefold()
        if character.isalnum()
    )


def _has_mismatched_explicit_version(
    expected_version: Optional[str],
    result_text: str,
) -> bool:
    normalized_expected = _normalized_version(expected_version)
    explicit_versions = _explicit_versions(result_text)
    return bool(
        normalized_expected
        and explicit_versions
        and normalized_expected not in explicit_versions
    )


def _known_issuer(request: FormAgentRequest) -> tuple[Optional[str], Optional[str]]:
    form_id = request.form_context.form_id
    form_version = request.form_context.form_version
    if form_id is None or form_version is None:
        return None, None
    resource = next(
        (
            candidate
            for candidate in GUIDANCE_RESOURCES
            if candidate.form_id == form_id
            and candidate.form_version == form_version
        ),
        None,
    )
    if resource is None:
        return None, None
    return resource.source.organization, urlparse(resource.source.url).hostname


def _source_quality(
    hostname: str,
    issuer_host: Optional[str],
) -> Literal[
    "issuing_organization",
    "public_authority",
    "general_web",
]:
    if issuer_host and (
        hostname == issuer_host or hostname.endswith(f".{issuer_host}")
    ):
        return "issuing_organization"
    if hostname.endswith(_PUBLIC_AUTHORITY_SUFFIXES):
        return "public_authority"
    return "general_web"


def _valid_public_host(hostname: str) -> bool:
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        labels = hostname.split(".")
        return all(
            label
            and len(label) <= 63
            and label[0].isalnum()
            and label[-1].isalnum()
            and all(character.isalnum() or character == "-" for character in label)
            for label in labels
        )
    return address.is_global


def _assess_selected_evidence(
    request: FormAgentRequest,
    lookup: WebGuidanceLookup,
    sources: list[WebGuidanceCitation],
    *,
    lacks_issuer_source: bool,
) -> _EvidenceAssessment:
    claim_topic = _claim_topic(request, lookup)
    if (
        claim_topic == "requiredness"
        and _has_active_field_requirement_conflict(request, sources)
    ):
        active_field_id = request_active_field_id(request)
        active_field = next(
            (
                field
                for field in request.fields
                if field.id == active_field_id
            ),
            None,
        )
        field_label = (
            truncate_text(active_field.label, 120)
            if active_field is not None
            else "the active field"
        )
        return _EvidenceAssessment(
            status="conflicting",
            reason=(
                "Relevant live sources make incompatible required/optional "
                f"claims about {field_label}. Treat this as unresolved and "
                "check the issuing organisation's instructions."
            ),
        )

    if lookup.topic in {"purpose", "requirements"} and lacks_issuer_source:
        return _EvidenceAssessment(
            status="limited",
            reason=(
                "No issuing-organisation source was identified. These live "
                "results are general guidance, not a definitive rule."
            ),
        )

    return _EvidenceAssessment(
        status="supported",
        reason=(
            "Tavily found live web guidance. These sources are current search "
            "results and have not been pre-reviewed by Formless."
        ),
    )


def _claim_topic(
    request: FormAgentRequest,
    lookup: WebGuidanceLookup,
) -> EvidenceClaimTopic:
    message = request_message(request)
    if _ACCEPTED_VALUES_PATTERN.search(message) is not None:
        return "accepted_values"
    if _FORMATTING_PATTERN.search(message) is not None:
        return "formatting"
    return {
        "meaning": "definition",
        "purpose": "purpose",
        "requirements": "requiredness",
        "where_to_find": "where_to_find",
    }[lookup.topic]


def _has_active_field_requirement_conflict(
    request: FormAgentRequest,
    sources: list[WebGuidanceCitation],
) -> bool:
    polarities: set[Literal["required", "optional"]] = set()
    for source in sources:
        for clause in _CLAUSE_SPLIT_PATTERN.split(source.snippet):
            if not clause or not _claim_targets_active_field(request, clause):
                continue
            if _NEGATIVE_REQUIREMENT_PATTERN.search(clause) is not None:
                polarities.add("optional")
            if _POSITIVE_REQUIREMENT_PATTERN.search(clause) is not None:
                polarities.add("required")
    return polarities == {"required", "optional"}


def _claim_targets_active_field(
    request: FormAgentRequest,
    clause: str,
) -> bool:
    active_field_id = request_active_field_id(request)
    active_field = next(
        (
            field
            for field in request.fields
            if field.id == active_field_id
        ),
        None,
    )
    if active_field is None:
        return False

    expected_form_codes = _form_codes(
        " ".join(
            part
            for part in (
                request.form_context.form_id,
                request.form_context.title,
            )
            if part
        )
    )
    clause_form_codes = _form_codes(clause)
    if (
        expected_form_codes
        and clause_form_codes
        and not expected_form_codes.intersection(clause_form_codes)
    ):
        return False
    if _has_mismatched_explicit_version(
        request.form_context.form_version,
        clause,
    ):
        return False

    active_field_text = " ".join(
        part
        for part in (
            active_field.id.replace("_", " ").replace("-", " "),
            active_field.label,
            field_question(active_field),
            active_field.section,
        )
        if part
    )
    active_locators = _field_locators(active_field_text)
    clause_locators = _field_locators(clause)
    if active_locators and clause_locators:
        return _locators_match(active_locators, clause_locators)

    active_tokens = _significant_tokens(
        " ".join((active_field.label, field_question(active_field))),
        _GENERIC_FIELD_TOKENS,
    )
    return _field_token_match(active_tokens, _relevance_tokens(clause))


def _field_locators(value: str) -> frozenset[str]:
    return frozenset(
        f"{match.group(1).casefold()}:{match.group(2).casefold()}"
        for match in _FIELD_LOCATOR_PATTERN.finditer(value)
    )


def _locators_match(
    active_locators: frozenset[str],
    claim_locators: frozenset[str],
) -> bool:
    active_by_kind: dict[str, set[str]] = {}
    claim_by_kind: dict[str, set[str]] = {}
    for locator in active_locators:
        kind, value = locator.split(":", maxsplit=1)
        active_by_kind.setdefault(kind, set()).add(value)
    for locator in claim_locators:
        kind, value = locator.split(":", maxsplit=1)
        claim_by_kind.setdefault(kind, set()).add(value)

    shared_kinds = active_by_kind.keys() & claim_by_kind.keys()
    if any(
        active_by_kind[kind].isdisjoint(claim_by_kind[kind])
        for kind in shared_kinds
    ):
        return False
    return bool(active_locators.intersection(claim_locators))
