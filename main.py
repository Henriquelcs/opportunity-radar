from __future__ import annotations

import argparse
import json
from typing import Any

from src.pipeline.opportunity_pipeline import (
    OpportunityPipeline,
)


def show_opportunity(
    position: int,
    item: dict[str, Any],
) -> None:
    """
    Exibe uma oportunidade ranqueada.
    """
    print("\n" + "=" * 78)
    print(
        f"#{position} | "
        f"SCORE: {item.get('opportunity_score', 0):.2f} | "
        f"NÍVEL: {item.get('opportunity_level', 'unknown')}"
    )
    print("=" * 78)

    print(
        f"Fonte: {item.get('source', 'unknown')}"
    )

    print(
        f"Título: {item.get('title', 'Sem título')}"
    )

    print(
        f"URL: {item.get('url', 'Não disponível')}"
    )

    categories = item.get(
        "pain_categories",
        [],
    )

    print(
        "Dores: "
        + (
            ", ".join(categories)
            if categories
            else "Não classificadas"
        )
    )

    print(
        "Scores:"
        f" dor={item.get('pain_score', 0):.2f}"
        f" urgência={item.get('urgency_score', 0):.2f}"
        f" engajamento={item.get('engagement_score', 0):.2f}"
        f" mercado={item.get('market_score', 0):.2f}"
        f" confiança={item.get('confidence_score', 0):.2f}"
    )


def build_parser() -> argparse.ArgumentParser:
    """
    Cria os argumentos da aplicação.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Opportunity Radar — coleta e ranking "
            "de oportunidades."
        )
    )

    parser.add_argument(
        "--query",
        default="manual repetitive workflow automation",
        help="Termo utilizado nas fontes.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limite de itens por fonte.",
    )

    parser.add_argument(
        "--minimum-score",
        type=float,
        default=0.0,
        help="Pontuação mínima para exibição.",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Quantidade máxima de oportunidades.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Exibe o resultado em JSON.",
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()

    pipeline = OpportunityPipeline()

    result = pipeline.run(
        query=args.query,
        limit_per_source=args.limit,
        minimum_score=args.minimum_score,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "collected_count": (
                        result.collected_count
                    ),
                    "pain_count": result.pain_count,
                    "opportunity_count": (
                        result.opportunity_count
                    ),
                    "collection_errors": (
                        result.collection_errors
                    ),
                    "opportunities": (
                        result.opportunities[:args.top]
                    ),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        return

    print("=" * 78)
    print("OPPORTUNITY RADAR")
    print("SPRINT 6 — OPPORTUNITY SCORING ENGINE")
    print("=" * 78)

    print(
        f"Publicações coletadas: "
        f"{result.collected_count}"
    )

    print(
        f"Publicações com dor: "
        f"{result.pain_count}"
    )

    print(
        f"Oportunidades classificadas: "
        f"{result.opportunity_count}"
    )

    if result.collection_errors:
        print("\nFontes com erro:")

        for source, error in (
            result.collection_errors.items()
        ):
            print(f"- {source}: {error}")

    if not result.opportunities:
        print(
            "\nNenhuma oportunidade encontrada "
            "com os critérios atuais."
        )
        return

    for position, item in enumerate(
        result.opportunities[:args.top],
        start=1,
    ):
        show_opportunity(
            position=position,
            item=item,
        )


if __name__ == "__main__":
    main()
