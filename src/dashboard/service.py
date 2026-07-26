from __future__ import annotations

from collections import Counter
from collections import defaultdict
from datetime import datetime
from typing import Any


LEVEL_ORDER = [
    "critical",
    "high",
    "medium",
    "low",
    "very_low",
]


LEVEL_LABELS = {
    "critical": "Crítica",
    "high": "Alta",
    "medium": "Média",
    "low": "Baixa",
    "very_low": "Muito baixa",
}


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Converte valores para float com segurança.
    """
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def parse_datetime(
    value: Any,
) -> datetime | None:
    """
    Converte uma data ISO em datetime.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


def format_datetime(
    value: Any,
) -> str:
    """
    Formata data para exibição.
    """
    parsed = parse_datetime(value)

    if parsed is None:
        return "Não informado"

    return parsed.strftime(
        "%d/%m/%Y %H:%M"
    )


def normalize_level(
    value: Any,
) -> str:
    """
    Normaliza o nível da oportunidade.
    """
    level = str(
        value or "very_low"
    ).strip().lower()

    if level not in LEVEL_LABELS:
        return "very_low"

    return level


def calculate_summary(
    opportunities: list[dict[str, Any]],
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Calcula os principais indicadores do dashboard.
    """
    total = len(opportunities)

    scores = [
        safe_float(
            item.get("opportunity_score")
        )
        for item in opportunities
    ]

    average_score = (
        sum(scores) / len(scores)
        if scores
        else 0.0
    )

    high_potential_count = sum(
        1
        for item in opportunities
        if normalize_level(
            item.get("opportunity_level")
        )
        in {
            "critical",
            "high",
        }
    )

    source_count = len(
        {
            str(
                item.get("source") or "unknown"
            )
            for item in opportunities
        }
    )

    last_run = runs[0] if runs else None

    return {
        "total_opportunities": total,
        "average_score": round(
            average_score,
            2,
        ),
        "high_potential_count": (
            high_potential_count
        ),
        "source_count": source_count,
        "last_run_status": (
            last_run.get(
                "execution_status",
                "NOT_EXECUTED",
            )
            if last_run
            else "NOT_EXECUTED"
        ),
        "last_run_at": (
            last_run.get("started_at")
            if last_run
            else None
        ),
    }


def build_source_distribution(
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Agrupa oportunidades por fonte.
    """
    counter = Counter(
        str(
            item.get("source") or "unknown"
        )
        for item in opportunities
    )

    return [
        {
            "source": source,
            "count": count,
        }
        for source, count in sorted(
            counter.items(),
            key=lambda pair: (
                pair[1],
                pair[0],
            ),
            reverse=True,
        )
    ]


def build_level_distribution(
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Agrupa oportunidades por classificação.
    """
    counter = Counter(
        normalize_level(
            item.get("opportunity_level")
        )
        for item in opportunities
    )

    return [
        {
            "level": level,
            "label": LEVEL_LABELS[level],
            "count": counter.get(
                level,
                0,
            ),
        }
        for level in LEVEL_ORDER
    ]


def build_average_scores_by_source(
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Calcula o score médio por fonte.
    """
    grouped_scores: dict[
        str,
        list[float],
    ] = defaultdict(list)

    for item in opportunities:
        source = str(
            item.get("source") or "unknown"
        )

        grouped_scores[source].append(
            safe_float(
                item.get(
                    "opportunity_score"
                )
            )
        )

    results = []

    for source, scores in (
        grouped_scores.items()
    ):
        average = (
            sum(scores) / len(scores)
            if scores
            else 0.0
        )

        results.append(
            {
                "source": source,
                "average_score": round(
                    average,
                    2,
                ),
                "count": len(scores),
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["average_score"],
            item["count"],
        ),
        reverse=True,
    )


def build_score_breakdown(
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Calcula médias de cada dimensão do score.
    """
    fields = {
        "Dor": "pain_score",
        "Urgência": "urgency_score",
        "Engajamento": (
            "engagement_score"
        ),
        "Mercado": "market_score",
        "Confiança": (
            "confidence_score"
        ),
    }

    results = []

    for label, field in fields.items():
        values = [
            safe_float(
                item.get(field)
            )
            for item in opportunities
        ]

        average = (
            sum(values) / len(values)
            if values
            else 0.0
        )

        results.append(
            {
                "dimension": label,
                "average_score": round(
                    average,
                    2,
                ),
            }
        )

    return results


def build_runs_history(
    runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Normaliza execuções para gráficos e tabelas.
    """
    normalized = []

    for run in runs:
        normalized.append(
            {
                "id": run.get("id"),
                "query": run.get(
                    "query",
                    "",
                ),
                "status": run.get(
                    "execution_status",
                    "UNKNOWN",
                ),
                "collected": int(
                    run.get(
                        "collected_count",
                        0,
                    )
                    or 0
                ),
                "pain": int(
                    run.get(
                        "pain_count",
                        0,
                    )
                    or 0
                ),
                "opportunities": int(
                    run.get(
                        "opportunity_count",
                        0,
                    )
                    or 0
                ),
                "persisted": int(
                    run.get(
                        "persisted_count",
                        0,
                    )
                    or 0
                ),
                "started_at": run.get(
                    "started_at"
                ),
                "started_at_label": (
                    format_datetime(
                        run.get(
                            "started_at"
                        )
                    )
                ),
                "errors": run.get(
                    "collection_errors",
                    {},
                ),
            }
        )

    return normalized


def filter_opportunities(
    opportunities: list[dict[str, Any]],
    sources: list[str] | None = None,
    levels: list[str] | None = None,
    minimum_score: float = 0.0,
    search_text: str = "",
) -> list[dict[str, Any]]:
    """
    Aplica filtros do dashboard.
    """
    source_filter = set(
        sources or []
    )

    level_filter = {
        normalize_level(level)
        for level in (
            levels or []
        )
    }

    search_term = (
        search_text.strip().lower()
    )

    filtered = []

    for item in opportunities:
        source = str(
            item.get("source") or "unknown"
        )

        level = normalize_level(
            item.get(
                "opportunity_level"
            )
        )

        score = safe_float(
            item.get(
                "opportunity_score"
            )
        )

        searchable_text = " ".join(
            [
                str(
                    item.get("title") or ""
                ),
                str(
                    item.get(
                        "description"
                    )
                    or ""
                ),
                source,
                " ".join(
                    item.get(
                        "pain_categories",
                        [],
                    )
                    or []
                ),
            ]
        ).lower()

        if (
            source_filter
            and source not in source_filter
        ):
            continue

        if (
            level_filter
            and level not in level_filter
        ):
            continue

        if score < minimum_score:
            continue

        if (
            search_term
            and search_term
            not in searchable_text
        ):
            continue

        filtered.append(item)

    return sorted(
        filtered,
        key=lambda item: (
            safe_float(
                item.get(
                    "opportunity_score"
                )
            ),
            safe_float(
                item.get(
                    "confidence_score"
                )
            ),
        ),
        reverse=True,
    )


def build_opportunity_table(
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Monta a tabela principal do dashboard.
    """
    rows = []

    for item in opportunities:
        level = normalize_level(
            item.get(
                "opportunity_level"
            )
        )

        rows.append(
            {
                "Score": safe_float(
                    item.get(
                        "opportunity_score"
                    )
                ),
                "Nível": (
                    LEVEL_LABELS[level]
                ),
                "Fonte": item.get(
                    "source",
                    "unknown",
                ),
                "Título": item.get(
                    "title",
                    "Sem título",
                ),
                "Dor": safe_float(
                    item.get(
                        "pain_score"
                    )
                ),
                "Urgência": safe_float(
                    item.get(
                        "urgency_score"
                    )
                ),
                "Engajamento": safe_float(
                    item.get(
                        "engagement_score"
                    )
                ),
                "Mercado": safe_float(
                    item.get(
                        "market_score"
                    )
                ),
                "Confiança": safe_float(
                    item.get(
                        "confidence_score"
                    )
                ),
                "Última captura": (
                    format_datetime(
                        item.get(
                            "last_seen_at"
                        )
                    )
                ),
                "URL": item.get(
                    "url",
                    "",
                ),
            }
        )

    return rows
