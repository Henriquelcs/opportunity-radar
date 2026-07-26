from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any


PAIN_CATEGORY_WEIGHTS = {
    "manual_work": 1.0,
    "repetitive_work": 1.0,
    "time_waste": 0.9,
    "integration_problem": 0.9,
    "data_problem": 0.8,
    "workflow_problem": 0.8,
    "cost_problem": 0.8,
    "reliability_problem": 0.9,
    "performance_problem": 0.7,
    "usability_problem": 0.7,
    "missing_feature": 0.6,
    "frustration": 0.6,
}


URGENCY_PATTERNS = {
    "critical": (
        r"\bcritical\b",
        r"\burgent\b",
        r"\bemergency\b",
        r"\bproduction is down\b",
        r"\bblocking production\b",
        r"\bdata loss\b",
        r"\bsecurity issue\b",
    ),
    "high": (
        r"\bblocking\b",
        r"\bbroken\b",
        r"\bdoes not work\b",
        r"\bdoesn't work\b",
        r"\bcannot use\b",
        r"\bcan't use\b",
        r"\bfailed\b",
        r"\bfailing\b",
        r"\bimmediately\b",
    ),
    "medium": (
        r"\bneed\b",
        r"\blooking for\b",
        r"\bhow can i\b",
        r"\bhow do i\b",
        r"\bproblem\b",
        r"\bissue\b",
        r"\bdifficult\b",
        r"\bfrustrating\b",
    ),
}


COMMERCIAL_PATTERNS = (
    r"\bpay for\b",
    r"\bwilling to pay\b",
    r"\bbudget\b",
    r"\bsubscription\b",
    r"\benterprise\b",
    r"\bcompany\b",
    r"\bteam\b",
    r"\bcustomers\b",
    r"\bclients\b",
    r"\bbusiness\b",
    r"\bworkflow\b",
    r"\bautomation\b",
    r"\bsaas\b",
)


SOLUTION_PATTERNS = (
    r"\bis there a tool\b",
    r"\bis there an app\b",
    r"\blooking for a tool\b",
    r"\blooking for software\b",
    r"\balternative to\b",
    r"\bautomate\b",
    r"\bautomation\b",
    r"\bintegration\b",
    r"\bapi\b",
    r"\bplugin\b",
    r"\bextension\b",
)


def _safe_number(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Converte um valor para número com segurança.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """
    Mantém uma pontuação dentro do intervalo permitido.
    """
    return max(minimum, min(maximum, value))


def _normalize_text(item: dict[str, Any]) -> str:
    """
    Combina os campos textuais utilizados na análise.
    """
    parts = [
        item.get("title"),
        item.get("description"),
        item.get("body"),
        item.get("text"),
        item.get("content"),
    ]

    return " ".join(
        str(part)
        for part in parts
        if part
    ).lower()


def _count_pattern_matches(
    text: str,
    patterns: tuple[str, ...],
) -> int:
    """
    Conta quantos padrões diferentes aparecem no texto.
    """
    return sum(
        1
        for pattern in patterns
        if re.search(pattern, text)
    )


def calculate_pain_score(
    item: dict[str, Any],
) -> float:
    """
    Calcula intensidade e diversidade dos sinais de dor.
    """
    categories = item.get("pain_categories") or []
    signals = item.get("pain_signals") or {}

    unique_categories = {
        str(category)
        for category in categories
        if category
    }

    signal_count = 0

    if isinstance(signals, dict):
        for matches in signals.values():
            if isinstance(matches, list):
                signal_count += len(matches)
            elif matches:
                signal_count += 1

    category_score = sum(
        PAIN_CATEGORY_WEIGHTS.get(
            category,
            0.5,
        )
        for category in unique_categories
    )

    raw_score = (
        category_score * 18.0
        + min(signal_count, 10) * 3.0
    )

    return round(_clamp(raw_score), 2)


def calculate_urgency_score(
    item: dict[str, Any],
) -> float:
    """
    Estima a urgência apresentada na publicação.
    """
    text = _normalize_text(item)

    critical_matches = _count_pattern_matches(
        text,
        URGENCY_PATTERNS["critical"],
    )

    high_matches = _count_pattern_matches(
        text,
        URGENCY_PATTERNS["high"],
    )

    medium_matches = _count_pattern_matches(
        text,
        URGENCY_PATTERNS["medium"],
    )

    raw_score = (
        critical_matches * 35.0
        + high_matches * 18.0
        + medium_matches * 7.0
    )

    return round(_clamp(raw_score), 2)


def calculate_engagement_score(
    item: dict[str, Any],
) -> float:
    """
    Normaliza sinais de engajamento vindos de fontes diferentes.
    """
    score = _safe_number(
        item.get(
            "score",
            item.get("votes", 0),
        )
    )

    comments = _safe_number(
        item.get(
            "comments",
            item.get(
                "comment_count",
                item.get("answers", 0),
            ),
        )
    )

    reactions = _safe_number(
        item.get(
            "reactions",
            item.get("likes", 0),
        )
    )

    views = _safe_number(
        item.get("views", 0)
    )

    followers = _safe_number(
        item.get(
            "followers",
            item.get("watchers", 0),
        )
    )

    raw_score = (
        math.log1p(max(score, 0)) * 18.0
        + math.log1p(max(comments, 0)) * 15.0
        + math.log1p(max(reactions, 0)) * 10.0
        + math.log1p(max(views, 0)) * 4.0
        + math.log1p(max(followers, 0)) * 3.0
    )

    return round(_clamp(raw_score), 2)


def calculate_market_score(
    item: dict[str, Any],
) -> float:
    """
    Estima potencial comercial e clareza de solução.
    """
    text = _normalize_text(item)

    commercial_matches = _count_pattern_matches(
        text,
        COMMERCIAL_PATTERNS,
    )

    solution_matches = _count_pattern_matches(
        text,
        SOLUTION_PATTERNS,
    )

    description_length = len(text.split())

    context_score = min(
        description_length / 2.0,
        20.0,
    )

    raw_score = (
        commercial_matches * 10.0
        + solution_matches * 9.0
        + context_score
    )

    return round(_clamp(raw_score), 2)


def calculate_confidence_score(
    item: dict[str, Any],
) -> float:
    """
    Calcula a confiança da análise com base na qualidade dos dados.
    """
    score = 0.0

    if item.get("title"):
        score += 20.0

    if (
        item.get("description")
        or item.get("body")
        or item.get("text")
        or item.get("content")
    ):
        score += 25.0

    if item.get("url"):
        score += 10.0

    if item.get("source"):
        score += 10.0

    if item.get("published_at"):
        score += 10.0

    if item.get("pain_categories"):
        score += 15.0

    if item.get("pain_signals"):
        score += 10.0

    return round(_clamp(score), 2)


def calculate_opportunity_score(
    pain_score: float,
    urgency_score: float,
    engagement_score: float,
    market_score: float,
    confidence_score: float,
) -> float:
    """
    Calcula a pontuação final ponderada.
    """
    weighted_score = (
        pain_score * 0.30
        + urgency_score * 0.20
        + engagement_score * 0.20
        + market_score * 0.20
        + confidence_score * 0.10
    )

    return round(
        _clamp(weighted_score),
        2,
    )


def classify_opportunity(
    score: float,
) -> str:
    """
    Classifica a oportunidade pela pontuação final.
    """
    if score >= 80:
        return "critical"

    if score >= 65:
        return "high"

    if score >= 45:
        return "medium"

    if score >= 25:
        return "low"

    return "very_low"


def score_opportunity(
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Analisa e pontua uma publicação normalizada.
    """
    scored_item = deepcopy(item)

    pain_score = calculate_pain_score(scored_item)
    urgency_score = calculate_urgency_score(scored_item)
    engagement_score = calculate_engagement_score(
        scored_item
    )
    market_score = calculate_market_score(scored_item)
    confidence_score = calculate_confidence_score(
        scored_item
    )

    opportunity_score = calculate_opportunity_score(
        pain_score=pain_score,
        urgency_score=urgency_score,
        engagement_score=engagement_score,
        market_score=market_score,
        confidence_score=confidence_score,
    )

    scored_item.update(
        {
            "pain_score": pain_score,
            "urgency_score": urgency_score,
            "engagement_score": engagement_score,
            "market_score": market_score,
            "confidence_score": confidence_score,
            "opportunity_score": opportunity_score,
            "opportunity_level": classify_opportunity(
                opportunity_score
            ),
        }
    )

    return scored_item


def score_opportunities(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Pontua e ordena oportunidades da maior para a menor.
    """
    scored_items = [
        score_opportunity(item)
        for item in items
    ]

    return sorted(
        scored_items,
        key=lambda item: (
            item.get("opportunity_score", 0),
            item.get("confidence_score", 0),
            item.get("engagement_score", 0),
        ),
        reverse=True,
    )
