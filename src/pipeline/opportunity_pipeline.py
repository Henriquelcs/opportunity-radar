from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.collectors.manager import CollectorManager
from src.processors.opportunity_scorer import (
    score_opportunities,
)


@dataclass(slots=True)
class PipelineResult:
    """
    Resultado completo da execução do pipeline.
    """

    collected_count: int
    pain_count: int
    opportunity_count: int
    opportunities: list[dict[str, Any]]
    collection_errors: dict[str, str]


class OpportunityPipeline:
    """
    Coordena coleta, detecção de dor e ranking.
    """

    def __init__(
        self,
        collector_manager: CollectorManager | None = None,
    ) -> None:
        self.collector_manager = (
            collector_manager
            or CollectorManager()
        )

    @staticmethod
    def _analyze_pain(
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Executa o detector já existente sem acoplar sua
        assinatura diretamente ao restante do pipeline.
        """
        from src.processors.pain_detector import (
            filter_items_with_pain,
        )

        return filter_items_with_pain(items)

    def run(
        self,
        query: str,
        limit_per_source: int = 20,
        minimum_score: float = 0.0,
    ) -> PipelineResult:
        """
        Executa todas as etapas do Opportunity Radar.
        """
        collection_result = (
            self.collector_manager.collect_all(
                query=query,
                limit=limit_per_source,
            )
        )

        collected_items = collection_result.items

        pain_items = self._analyze_pain(
            collected_items
        )

        ranked_items = score_opportunities(
            pain_items
        )

        opportunities = [
            item
            for item in ranked_items
            if item.get(
                "opportunity_score",
                0.0,
            ) >= minimum_score
        ]

        return PipelineResult(
            collected_count=len(collected_items),
            pain_count=len(pain_items),
            opportunity_count=len(opportunities),
            opportunities=opportunities,
            collection_errors=collection_result.errors,
        )
