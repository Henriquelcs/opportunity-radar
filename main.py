from src.collectors.hackernews import (
    HackerNewsCollector,
)
from src.config.settings import (
    DEFAULT_COLLECTION_LIMIT,
)


def show_item(item: dict) -> None:
    """
    Mostra uma publicação no terminal.
    """
    print("-" * 60)

    print(
        f"ID: {item.get('id')}"
    )

    print(
        f"Título: {item.get('title', 'Sem título')}"
    )

    print(
        f"Autor: {item.get('by', 'Desconhecido')}"
    )

    print(
        f"Pontuação: {item.get('score', 0)}"
    )

    print(
        f"Comentários: "
        f"{item.get('descendants', 0)}"
    )


def main() -> None:
    """
    Executa uma coleta simples para validação.
    """
    print("=" * 60)
    print("OPPORTUNITY RADAR")
    print("ETAPA 2 — COLETOR HACKER NEWS")
    print("=" * 60)

    collector = HackerNewsCollector()

    items = collector.collect(
        limit=DEFAULT_COLLECTION_LIMIT
    )

    print(
        f"\nPublicações coletadas: {len(items)}"
    )

    for item in items[:5]:
        show_item(item)


if __name__ == "__main__":
    main()
