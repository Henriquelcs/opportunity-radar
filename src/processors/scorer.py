from __future__ import annotations

from typing import Any


CATEGORY_WEIGHTS: dict[str, int] = {
    "manual_work": 20,
    "time_waste": 20,
    "repetitive_work": 15,
    "frustration": 15,
    "missing_solution": 20,
    "problem_report": 10,
}


def calculate_engagement_score(
    item: dict[str, Any],
) -> int:
    """
    Calcula até 20 pontos por engajamento.

    Considera:
    - score da publicação;
    - quantidade de comentários.
    """
    publication_score = max(
        int(item.get("score", 0) or 0),
        0,
    )

    comments = max(
        int(item.get("descendants", 0) or 0),
        0,
    )

    points = 0

    if publication_score >= 300:
        points += 10
    elif publication_score >= 100:
        points += 7
    elif publication_score >= 30:
        points += 4
    elif publication_score >= 10:
        points += 2

    if comments >= 150:
        points += 10
    elif comments >= 50:
        points += 7
    elif comments >= 10:
        points += 4
    elif comments >= 1:
        points += 2

    return min(points, 20)


def calculate_pain_score(
    item: dict[str, Any],
) -> int:
    """
    Calcula até 80 pontos pelas dores detectadas.
    """
    categories = item.get(
        "pain_categories",
        [],
    )

    unique_categories = set(categories)

    score = sum(
        CATEGORY_WEIGHTS.get(category, 0)
        for category in unique_categories
    )

    return min(score, 80)


def calculate_opportunity_score(
    item: dict[str, Any],
) -> int:
    """
    Calcula o score total de oportunidade.

    Score máximo: 100 pontos.
    """
    pain_score = calculate_pain_score(item)
    engagement_score = calculate_engagement_score(
        item
    )

    return min(
        pain_score + engagement_score,
        100,
    )


def classify_opportunity(
    score: int,
) -> str:
    """
    Classifica a oportunidade conforme o score.
    """
    if score >= 75:
        return "alta"

    if score >= 50:
        return "media"

    if score >= 25:
        return "baixa"

    return "muito_baixa"


def score_item(
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Adiciona score e classificação à publicação.
    """
    scored_item = dict(item)

    pain_score = calculate_pain_score(item)
    engagement_score = calculate_engagement_score(
        item
    )
    opportunity_score = calculate_opportunity_score(
        item
    )

    scored_item["pain_score"] = pain_score
    scored_item[
        "engagement_score"
    ] = engagement_score
    scored_item[
        "opportunity_score"
    ] = opportunity_score
    scored_item[
        "opportunity_level"
    ] = classify_opportunity(
        opportunity_score
    )

    return scored_item


def rank_opportunities(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Pontua e ordena as oportunidades
    do maior para o menor score.
    """
    scored_items = [
        score_item(item)
        for item in items
    ]

    return sorted(
        scored_items,
        key=lambda item: (
            item["opportunity_score"],
            item.get("score", 0),
            item.get("descendants", 0),
        ),
        reverse=True,
    )
