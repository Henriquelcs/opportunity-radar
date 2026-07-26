from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit, urlunsplit


AUTOMATIC_TITLE_PATTERNS = (
    re.compile(
        r"\bofficial\s+ai\s+content\s+report\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bproduct\s+hunt\s+ai\s+digest\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bopenclaw\s+ecosystem\s+digest\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bglobal\s+tech\s+briefing\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*org\s+status\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*check\s+trending\s+repo\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*daily\s+security\s+audit\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(daily|weekly|monthly)\s+"
        r"(digest|newsletter|briefing)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*\[wiki\s+c\d+\]\s+migrate\b",
        re.IGNORECASE,
    ),
)


AUTOMATIC_URL_PATTERNS = (
    re.compile(
        r"github\.com/[^/]+/agents-radar/",
        re.IGNORECASE,
    ),
    re.compile(
        r"github\.com/[^/]+/trending-watcher/",
        re.IGNORECASE,
    ),
)


META_TITLE_PATTERNS = (
    re.compile(
        r"^\s*(prd|spec|specification|epic)\s*:",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(chore|feat\(ci\)|fix\(ci)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*\[wiki\b",
        re.IGNORECASE,
    ),
)


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "automation",
    "da",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "error",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "para",
    "the",
    "to",
    "with",
}


TEXT_FIELDS = (
    "title",
    "body",
    "description",
    "summary",
    "text",
    "content",
    "pain_summary",
    "problem",
    "tags",
    "repository",
)


def normalize_text(value: Any) -> str:
    text = str(value or "")

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    text = text.lower()

    text = re.sub(
        r"https?://\S+",
        " ",
        text,
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


def canonicalize_url(value: Any) -> str:
    raw_url = str(value or "").strip()

    if not raw_url:
        return ""

    try:
        parts = urlsplit(raw_url)

        path = parts.path.rstrip("/")

        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                path,
                "",
                "",
            )
        )
    except ValueError:
        return raw_url.lower().rstrip("/")


def query_tokens(query: str) -> set[str]:
    normalized = normalize_text(query)

    return {
        token
        for token in normalized.split()
        if len(token) >= 3
        and token not in STOPWORDS
    }


def item_text(item: dict[str, Any]) -> str:
    values = []

    for field in TEXT_FIELDS:
        value = item.get(field)

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            values.extend(
                str(part)
                for part in value
            )
        elif value:
            values.append(
                str(value)
            )

    return normalize_text(
        " ".join(values)
    )


def calculate_relevance(
    item: dict[str, Any],
    query: str,
) -> float:
    tokens = query_tokens(query)

    if not tokens:
        return 1.0

    document_tokens = set(
        item_text(item).split()
    )

    matches = tokens.intersection(
        document_tokens
    )

    return round(
        len(matches) / len(tokens),
        4,
    )


def is_noise_opportunity(
    item: dict[str, Any],
) -> bool:
    title = str(
        item.get("title") or ""
    )

    url = str(
        item.get("url")
        or item.get("html_url")
        or ""
    )

    if any(
        pattern.search(title)
        for pattern in AUTOMATIC_TITLE_PATTERNS
    ):
        return True

    if any(
        pattern.search(url)
        for pattern in AUTOMATIC_URL_PATTERNS
    ):
        return True

    return False


def is_irrelevant_meta_issue(
    item: dict[str, Any],
    query: str,
) -> bool:
    source = normalize_text(
        item.get("source")
    )

    if source != "github":
        return False

    title = str(
        item.get("title") or ""
    )

    if not any(
        pattern.search(title)
        for pattern in META_TITLE_PATTERNS
    ):
        return False

    relevance = calculate_relevance(
        item,
        query,
    )

    score = float(
        item.get("opportunity_score")
        or item.get("score")
        or 0.0
    )

    return (
        relevance == 0.0
        and score < 65.0
    )


def opportunity_identity(
    item: dict[str, Any],
) -> str:
    url = canonicalize_url(
        item.get("url")
        or item.get("html_url")
    )

    if url:
        return f"url:{url}"

    source = normalize_text(
        item.get("source")
    )

    title = normalize_text(
        item.get("title")
    )

    return f"title:{source}:{title}"


def filter_opportunities(
    opportunities: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    filtered = []
    seen = set()

    for opportunity in opportunities:
        if not isinstance(
            opportunity,
            dict,
        ):
            continue

        if is_noise_opportunity(
            opportunity
        ):
            continue

        if is_irrelevant_meta_issue(
            opportunity,
            query,
        ):
            continue

        identity = opportunity_identity(
            opportunity
        )

        if identity in seen:
            continue

        seen.add(identity)
        filtered.append(opportunity)

    return filtered
