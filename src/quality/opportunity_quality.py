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
        r"\bjob\s+radar\s+batch\b",
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
        r"^\s*audit\s*/?\s*review\s+update\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(daily|weekly|monthly)\s+"
        r"(digest|newsletter|briefing|report)\b",
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
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
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


GENERIC_INTENT_TOKENS = {
    "automation",
    "repetition",
    "manual",
    "workflow",
    "error",
}


TOKEN_ALIASES = {
    "automate": "automation",
    "automated": "automation",
    "automates": "automation",
    "automating": "automation",
    "automatic": "automation",
    "automatically": "automation",
    "automation": "automation",

    "repeat": "repetition",
    "repeated": "repetition",
    "repeating": "repetition",
    "repetitive": "repetition",
    "repetition": "repetition",

    "excel": "spreadsheet",
    "sheet": "spreadsheet",
    "sheets": "spreadsheet",
    "spreadsheet": "spreadsheet",
    "spreadsheets": "spreadsheet",

    "client": "customer",
    "clients": "customer",
    "customer": "customer",
    "customers": "customer",

    "helpdesk": "support",
    "ticket": "support",
    "tickets": "support",
    "ticketing": "support",
    "support": "support",

    "bug": "error",
    "bugs": "error",
    "error": "error",
    "errors": "error",
    "exception": "error",
    "exceptions": "error",
    "failure": "error",
    "failures": "error",

    "manual": "manual",
    "manually": "manual",

    "workflow": "workflow",
    "workflows": "workflow",

    "entry": "entry",
    "entries": "entry",

    "data": "data",

    "integration": "integration",
    "integrations": "integration",
    "integrate": "integration",
}


# Somente conteúdo original da fonte.
# Campos produzidos pelo analisador não podem validar relevância.
SOURCE_TEXT_FIELDS = (
    "title",
    "body",
    "description",
    "summary",
    "text",
    "content",
    "tags",
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

    return " ".join(text.split())


def canonical_token(token: str) -> str:
    normalized = normalize_text(token)

    if not normalized:
        return ""

    return TOKEN_ALIASES.get(
        normalized,
        normalized,
    )


def extract_tokens(value: Any) -> set[str]:
    normalized = normalize_text(value)

    return {
        canonical_token(token)
        for token in normalized.split()
        if len(token) >= 3
        and token not in STOPWORDS
    }


def query_tokens(query: str) -> set[str]:
    return extract_tokens(query)


def source_text(item: dict[str, Any]) -> str:
    values = []

    for field in SOURCE_TEXT_FIELDS:
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
            values.append(str(value))

    return " ".join(values)


def relevance_evidence(
    item: dict[str, Any],
    query: str,
) -> dict[str, Any]:
    expected_tokens = query_tokens(query)

    title_tokens = extract_tokens(
        item.get("title")
    )

    document_tokens = extract_tokens(
        source_text(item)
    )

    domain_tokens = (
        expected_tokens
        - GENERIC_INTENT_TOKENS
    )

    intent_tokens = (
        expected_tokens
        & GENERIC_INTENT_TOKENS
    )

    return {
        "query_tokens": expected_tokens,
        "domain_tokens": domain_tokens,
        "intent_tokens": intent_tokens,
        "title_matches": (
            expected_tokens & title_tokens
        ),
        "domain_matches": (
            domain_tokens & document_tokens
        ),
        "intent_matches": (
            intent_tokens & document_tokens
        ),
        "document_matches": (
            expected_tokens & document_tokens
        ),
    }


def calculate_relevance(
    item: dict[str, Any],
    query: str,
) -> float:
    evidence = relevance_evidence(
        item,
        query,
    )

    expected = evidence["query_tokens"]

    if not expected:
        return 1.0

    return round(
        len(evidence["document_matches"])
        / len(expected),
        4,
    )


def is_query_relevant(
    item: dict[str, Any],
    query: str,
) -> bool:
    evidence = relevance_evidence(
        item,
        query,
    )

    query_token_set = evidence[
        "query_tokens"
    ]

    if not query_token_set:
        return True

    domain_tokens = evidence[
        "domain_tokens"
    ]

    intent_tokens = evidence[
        "intent_tokens"
    ]

    # Consulta genérica isolada, como "automation".
    # A análise de dor anterior determina a qualidade.
    if (
        not domain_tokens
        and len(query_token_set) == 1
    ):
        return True

    if domain_tokens:
        # Os termos específicos da pesquisa precisam
        # estar presentes no título da publicação.
        #
        # Exemplo:
        # "repetitive data entry" exige "data" e "entry"
        # no título. Apenas "repetitive input" não passa.
        title_domain_matches = (
            evidence["title_matches"]
            & domain_tokens
        )

        if title_domain_matches != domain_tokens:
            return False

        # Confirma que todos os termos específicos
        # também estão no conteúdo original.
        if (
            evidence["domain_matches"]
            != domain_tokens
        ):
            return False

        # Exige a intenção da pesquisa:
        # automação, repetição, erro etc.
        if (
            intent_tokens
            and not evidence["intent_matches"]
        ):
            return False

        return True

    # Consultas formadas apenas por termos genéricos.
    required_matches = min(
        2,
        len(query_token_set),
    )

    return (
        len(evidence["document_matches"])
        >= required_matches
    )

def canonicalize_url(value: Any) -> str:
    raw_url = str(value or "").strip()

    if not raw_url:
        return ""

    try:
        parts = urlsplit(raw_url)

        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path.rstrip("/"),
                "",
                "",
            )
        )

    except ValueError:
        return raw_url.lower().rstrip("/")


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

    return not is_query_relevant(
        item,
        query,
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

        if not is_query_relevant(
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
