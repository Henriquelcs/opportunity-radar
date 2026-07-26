from dataclasses import dataclass
from typing import Any

from src.pipeline.opportunity_pipeline import (
    OpportunityPipeline,
)
from src.storage.opportunity_repository import (
    CollectionRunRepository,
)
from src.storage.opportunity_repository import (
    OpportunityRepository,
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


def build_pipeline(
    tmp_path,
    collector_manager,
):
    database_path = (
        tmp_path / "pipeline.db"
    )

    return OpportunityPipeline(
        collector_manager=collector_manager,
        repository=OpportunityRepository(
            database_path
        ),
        run_repository=CollectionRunRepository(
            database_path
        ),
    )


def test_pipeline_collects_scores_and_persists(
    tmp_path,
):
    pipeline = build_pipeline(
        tmp_path,
        FakeCollectorManager(),
    )

    result = pipeline.run(
        query="automation",
        limit_per_source=10,
    )

    assert result.collected_count == 2
    assert result.pain_count == 1
    assert result.opportunity_count == 1
    assert result.persisted_count == 1
    assert result.execution_status == "SUCCESS"
    assert result.run_id is not None

    assert pipeline.repository.count() == 1

    opportunity = result.opportunities[0]

    assert opportunity["id"] == "1"
    assert opportunity["opportunity_score"] > 0


def test_pipeline_filters_minimum_score(
    tmp_path,
):
    pipeline = build_pipeline(
        tmp_path,
        FakeCollectorManager(),
    )

    result = pipeline.run(
        query="automation",
        limit_per_source=10,
        minimum_score=101,
    )

    assert result.collected_count == 2
    assert result.pain_count == 1
    assert result.opportunity_count == 0
    assert result.persisted_count == 0


def test_pipeline_can_disable_persistence(
    tmp_path,
):
    pipeline = build_pipeline(
        tmp_path,
        FakeCollectorManager(),
    )

    result = pipeline.run(
        query="automation",
        limit_per_source=10,
        persist=False,
    )

    assert result.opportunity_count == 1
    assert result.persisted_count == 0
    assert pipeline.repository.count() == 0


def test_pipeline_preserves_collection_errors(
    tmp_path,
):
    pipeline = build_pipeline(
        tmp_path,
        FailedCollectorManager(),
    )

    result = pipeline.run(
        query="automation",
        limit_per_source=10,
    )

    assert result.collection_errors == {
        "producthunt": "Unauthorized",
    }

    assert (
        result.execution_status
        == "PARTIAL_SUCCESS"
    )

    assert result.opportunity_count == 0

    runs = (
        pipeline.run_repository.list_recent()
    )

    assert len(runs) == 1

    assert (
        runs[0]["execution_status"]
        == "PARTIAL_SUCCESS"
    )
