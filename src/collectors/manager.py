from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.collectors.github_issues import (
    GitHubIssuesCollector,
)
from src.collectors.producthunt import (
    ProductHuntCollector,
)
from src.collectors.stackoverflow import (
    StackOverflowCollector,
)


class CollectorProtocol(Protocol):
    def collect(
        self,
        limit: int = 30,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        ...


@dataclass
class CollectionResult:
    items: list[dict[str, Any]] = field(
        default_factory=list
    )
    errors: dict[str, str] = field(
        default_factory=dict
    )
    source_counts: dict[str, int] = field(
        default_factory=dict
    )

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def successful_sources(self) -> list[str]:
        return [
            source
            for source in self.source_counts
            if source not in self.errors
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "errors": self.errors,
            "source_counts": self.source_counts,
            "total_items": self.total_items,
            "successful_sources": (
                self.successful_sources
            ),
        }


class CollectorManager:
    """
    Executa múltiplos collectors com isolamento de falhas.
    """

    def __init__(
        self,
        collectors: (
            dict[str, CollectorProtocol] | None
        ) = None,
    ) -> None:
        self.collectors = collectors or (
            self._build_default_collectors()
        )

    @staticmethod
    def _build_default_collectors(
    ) -> dict[str, CollectorProtocol]:
        return {
            "github": GitHubIssuesCollector(),
            "stackoverflow": StackOverflowCollector(),
            "producthunt": ProductHuntCollector(),
        }

    @staticmethod
    def _deduplicate(
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        unique_items: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        for item in items:
            item_id = str(item.get("id") or "")
            item_url = str(item.get("url") or "")

            deduplication_key = (
                item_id
                or item_url
                or (
                    f"{item.get('source', '')}:"
                    f"{item.get('title', '')}"
                )
            )

            if deduplication_key in seen_keys:
                continue

            seen_keys.add(deduplication_key)
            unique_items.append(item)

        return unique_items

    def collect_source(
        self,
        source: str,
        *,
        limit: int = 30,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if source not in self.collectors:
            available_sources = ", ".join(
                sorted(self.collectors)
            )

            raise ValueError(
                f"Collector desconhecido: {source}. "
                f"Disponíveis: {available_sources}"
            )

        return self.collectors[source].collect(
            limit=limit,
            **kwargs,
        )

    def collect_all(
        self,
        *,
        limit_per_source: int = 30,
        sources: list[str] | None = None,
        source_options: (
            dict[str, dict[str, Any]] | None
        ) = None,
        fail_fast: bool = False,
    ) -> CollectionResult:
        selected_sources = (
            sources
            if sources is not None
            else list(self.collectors.keys())
        )

        options = source_options or {}
        collected_items: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        source_counts: dict[str, int] = {}

        for source in selected_sources:
            if source not in self.collectors:
                message = (
                    f"Collector desconhecido: {source}"
                )

                if fail_fast:
                    raise ValueError(message)

                errors[source] = message
                source_counts[source] = 0
                continue

            collector = self.collectors[source]
            collector_options = options.get(source, {})

            try:
                source_items = collector.collect(
                    limit=limit_per_source,
                    **collector_options,
                )

                normalized_items = []

                for item in source_items:
                    normalized_item = dict(item)
                    normalized_item.setdefault(
                        "source",
                        source,
                    )
                    normalized_items.append(
                        normalized_item
                    )

                source_counts[source] = len(
                    normalized_items
                )
                collected_items.extend(
                    normalized_items
                )

            except Exception as error:
                if fail_fast:
                    raise

                errors[source] = (
                    f"{type(error).__name__}: {error}"
                )
                source_counts[source] = 0

        return CollectionResult(
            items=self._deduplicate(collected_items),
            errors=errors,
            source_counts=source_counts,
        )
