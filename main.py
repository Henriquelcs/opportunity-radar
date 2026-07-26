from src.collectors.hackernews import (
    HackerNewsCollector,
)
from src.config.settings import (
    DEFAULT_COLLECTION_LIMIT,
)
from src.processors.pain_detector import (
    filter_items_with_pain,
)
from src.processors.scorer import (
    rank_opportunities,
)


def show_opportunity(
    position: int,
    item: dict,
) -> None:
    """
    Mostra uma oportunidade pontuada.
    """
    print("-" * 70)
    print(f"Ranking: #{position}")
    print(f"ID: {item.get('id')}")
    print(
        f"Título: "
        f"{item.get('title', 'Sem título')}"
    )
    print(
        f"Score da oportunidade: "
        f"{item['opportunity_score']}/100"
    )
    print(
        f"Classificação: "
        f"{item['opportunity_level']}"
    )
    print(
        f"Score de dor: "
        f"{item['pain_score']}/80"
    )
    print(
        f"Score de engajamento: "
        f"{item['engagement_score']}/20"
    )
    print(
        "Categorias: "
        f"{', '.join(item['pain_categories'])}"
    )


def main() -> None:
    print("=" * 70)
    print("OPPORTUNITY RADAR")
    print("ETAPA 4 — SCORE DE OPORTUNIDADES")
    print("=" * 70)

    collector = HackerNewsCollector()

    collected_items = collector.collect(
        limit=DEFAULT_COLLECTION_LIMIT
    )

    pain_items = filter_items_with_pain(
        collected_items
    )

    ranked_items = rank_opportunities(
        pain_items
    )

    print(
        f"\nPublicações coletadas: "
        f"{len(collected_items)}"
    )

    print(
        f"Possíveis dores: "
        f"{len(pain_items)}"
    )

    print(
        f"Oportunidades pontuadas: "
        f"{len(ranked_items)}"
    )

    if not ranked_items:
        print(
            "\nNenhuma oportunidade encontrada "
            "nesta coleta."
        )
        return

    print("\nTOP OPORTUNIDADES")

    for position, item in enumerate(
        ranked_items[:10],
        start=1,
    ):
        show_opportunity(
            position,
            item,
        )


if __name__ == "__main__":
    main()
