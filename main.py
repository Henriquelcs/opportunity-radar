from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.pipeline.opportunity_pipeline import (
    OpportunityPipeline,
)
from src.storage.database import (
    DEFAULT_DATABASE_PATH,
)
from src.storage.opportunity_repository import (
    OpportunityRepository,
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
        f"SCORE: "
        f"{item.get('opportunity_score', 0):.2f} | "
        f"NÍVEL: "
        f"{item.get('opportunity_level', 'unknown')}"
    )

    print("=" * 78)

    print(
        f"Fonte: "
        f"{item.get('source', 'unknown')}"
    )

    print(
        f"Título: "
        f"{item.get('title', 'Sem título')}"
    )

    print(
        f"URL: "
        f"{item.get('url', 'Não disponível')}"
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
        f" urgência="
        f"{item.get('urgency_score', 0):.2f}"
        f" engajamento="
        f"{item.get('engagement_score', 0):.2f}"
        f" mercado="
        f"{item.get('market_score', 0):.2f}"
        f" confiança="
        f"{item.get('confidence_score', 0):.2f}"
    )


def build_parser() -> argparse.ArgumentParser:
    """
    Cria os argumentos da aplicação.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Opportunity Radar — coleta, ranking "
            "e persistência de oportunidades."
        )
    )

    parser.add_argument(
        "--query",
        default=(
            "manual repetitive workflow automation"
        ),
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
        help="Pontuação mínima.",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Quantidade máxima para exibição.",
    )

    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE_PATH),
        help="Caminho do banco SQLite.",
    )

    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Executa sem salvar oportunidades.",
    )

    parser.add_argument(
        "--list-stored",
        action="store_true",
        help="Lista oportunidades já armazenadas.",
    )

    parser.add_argument(
        "--source",
        default=None,
        help="Filtra oportunidades armazenadas por fonte.",
    )

    parser.add_argument(
        "--level",
        default=None,
        help="Filtra oportunidades por nível.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Exibe o resultado em JSON.",
    )

    return parser


def show_json(
    payload: dict[str, Any],
) -> None:
    """
    Exibe dados estruturados em JSON.
    """
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


def list_stored_opportunities(
    database_path: Path,
    minimum_score: float,
    top: int,
    source: str | None,
    level: str | None,
    json_output: bool,
) -> None:
    """
    Lista oportunidades persistidas.
    """
    repository = OpportunityRepository(
        database_path=database_path
    )

    opportunities = repository.list_ranked(
        limit=top,
        minimum_score=minimum_score,
        source=source,
        level=level,
    )

    if json_output:
        show_json(
            {
                "stored_count": (
                    repository.count()
                ),
                "returned_count": len(
                    opportunities
                ),
                "opportunities": opportunities,
            }
        )
        return

    print("=" * 78)
    print("OPPORTUNITY RADAR — BANCO DE DADOS")
    print("=" * 78)

    print(
        f"Total armazenado: "
        f"{repository.count()}"
    )

    print(
        f"Resultados retornados: "
        f"{len(opportunities)}"
    )

    for position, item in enumerate(
        opportunities,
        start=1,
    ):
        show_opportunity(position, item)


def main() -> None:
    args = build_parser().parse_args()

    database_path = Path(args.database)

    if args.list_stored:
        list_stored_opportunities(
            database_path=database_path,
            minimum_score=args.minimum_score,
            top=args.top,
            source=args.source,
            level=args.level,
            json_output=args.json,
        )
        return

    pipeline = OpportunityPipeline(
        database_path=database_path
    )

    result = pipeline.run(
        query=args.query,
        limit_per_source=args.limit,
        minimum_score=args.minimum_score,
        persist=not args.no_persist,
    )

    if args.json:
        show_json(
            {
                "run_id": result.run_id,
                "execution_status": (
                    result.execution_status
                ),
                "collected_count": (
                    result.collected_count
                ),
                "pain_count": result.pain_count,
                "opportunity_count": (
                    result.opportunity_count
                ),
                "persisted_count": (
                    result.persisted_count
                ),
                "collection_errors": (
                    result.collection_errors
                ),
                "opportunities": (
                    result.opportunities[
                        :args.top
                    ]
                ),
            }
        )
        return

    print("=" * 78)
    print("OPPORTUNITY RADAR")
    print("SPRINT 7 — SQLITE PERSISTENCE")
    print("=" * 78)

    print(
        f"Status: {result.execution_status}"
    )

    print(
        f"Execução registrada: "
        f"{result.run_id}"
    )

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

    print(
        f"Oportunidades persistidas: "
        f"{result.persisted_count}"
    )

    if result.collection_errors:
        print("\nFontes com erro:")

        for source, error in (
            result.collection_errors.items()
        ):
            print(
                f"- {source}: {error}"
            )

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
