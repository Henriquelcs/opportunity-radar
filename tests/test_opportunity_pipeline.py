from dataclasses import dataclass
from typing import Any

from src.pipeline.opportunity_pipeline import (
    OpportunityPipeline,
)


@dataclass
class FakeCollectionResult:
    items: list[dict[str, Any]]
    errors: dict[str, str]


class FakeCollectorManager:
    def collect_all(
        self,
        query: str,
        limit: int,
    ) -> FakeCollectionResult:
        assert query == "automation"
        assert limit == 10

        return FakeCollectionResult(
            items=[
                {
                    "id": "1",
                    "source": "github",
                    "title": (
                        "Manual repetitive workflow"
                    ),
                    "description": (
                        "Our team manually copies data "
                        "every day and needs automation."
                    ),
                    "url": "https://example.com/1",
                    "score": 20,
                    "comments": 10,
                },
                {
                    "id": "2",
                    "source": "stackoverflow",
                    "title": "Python release notes",
                    "description": (
                        "Information about a new release."
                    ),
                    "url": "https://example.com/2",
                },
            ],
            errors={},
        )


def test_pipeline_collects_analyzes_and_scores():
    pipeline = OpportunityPipeline(
        collector_manager=FakeCollectorManager()
    )

    result = pipeline.run(
        query="automation",
        limit_per_source=10,
    )

    assert result.collected_count == 2
    assert result.pain_count == 1
    assert result.opportunity_count == 1

    opportunity = result.opportunities[0]

    assert opportunity["id"] == "1"
    assert opportunity["opportunity_score"] > 0


def test_pipeline_filters_minimum_score():
    pipeline = OpportunityPipeline(
        collector_manager=FakeCollectorManager()
    )

    result = pipeline.run(
        query="automation",
        limit_per_source=10,
        minimum_score=101,
    )

    assert result.collected_count == 2
    assert result.pain_count == 1
    assert result.opportunity_count == 0


class FailedCollectorManager:
    def collect_all(
        self,
        query: str,
        limit: int,
    ) -> FakeCollectionResult:
        return FakeCollectionResult(
            items=[],
            errors={
                "producthunt": "Unauthorized",
            },
        )


def test_pipeline_preserves_collection_errors():
    pipeline = OpportunityPipeline(
        collector_manager=FailedCollectorManager()
    )

    result = pipeline.run(
        query="automation",
        limit_per_source=10,
    )

    assert result.collection_errors == {
        "producthunt": "Unauthorized",
    }

    assert result.opportunity_count == 0
