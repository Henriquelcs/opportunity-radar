from src.collectors.hackernews import (
    HackerNewsCollector,
)
from src.config.settings import (
    DEFAULT_COLLECTION_LIMIT,
)
from src.processors.pain_detector import (
    filter_items_with_pain,
)


def show_opportunity(item: dict) -> None:
    """
    Mostra uma publicação com sinal de dor.
    """
    print("-" * 70)
    print(f"ID: {item.get('id')}")
    print(
        f"Título: "
        f"{item.get('title', 'Sem título')}"
    )
    print(
        "Categorias de dor: "
        f"{', '.join(item['pain_categories'])}"
    )

    print("Sinais encontrados:")

    for category, matches in item[
        "pain_signals"
    ].items():
        print(
            f"  - {category}: "
            f"{', '.join(matches)}"
        )


def main() -> None:
    print("=" * 70)
    print("OPPORTUNITY RADAR")
    print("ETAPA 3 — DETECTOR DE SINAIS DE DOR")
    print("=" * 70)

    collector = HackerNewsCollector()

    collected_items = collector.collect(
        limit=DEFAULT_COLLECTION_LIMIT
    )

    pain_items = filter_items_with_pain(
        collected_items
    )

    print(
        f"\nPublicações coletadas: "
        f"{len(collected_items)}"
    )

    print(
        f"Possíveis dores identificadas: "
        f"{len(pain_items)}"
    )

    if not pain_items:
        print(
            "\nNenhum sinal de dor foi encontrado "
            "nesta coleta."
        )
        return

    for item in pain_items[:10]:
        show_opportunity(item)


if __name__ == "__main__":
    main()
