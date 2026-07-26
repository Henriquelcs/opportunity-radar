from src.storage.opportunity_repository import (
    CollectionRunRepository,
)
from src.storage.opportunity_repository import (
    OpportunityRepository,
)


def build_opportunity(
    external_id="123",
    score=75.0,
):
    return {
        "id": external_id,
        "source": "github",
        "title": "Manual repetitive workflow",
        "description": (
            "Our team needs automation."
        ),
        "url": (
            f"https://example.com/{external_id}"
        ),
        "author": "user",
        "published_at": (
            "2026-07-26T10:00:00Z"
        ),
        "pain_categories": [
            "manual_work",
        ],
        "pain_signals": {
            "manual_work": ["manual"],
        },
        "metadata": {
            "repository": "example/test",
        },
        "pain_score": 70.0,
        "urgency_score": 50.0,
        "engagement_score": 40.0,
        "market_score": 80.0,
        "confidence_score": 90.0,
        "opportunity_score": score,
        "opportunity_level": "high",
    }


def test_upsert_inserts_opportunity(tmp_path):
    repository = OpportunityRepository(
        tmp_path / "test.db"
    )

    record_id = repository.upsert(
        build_opportunity()
    )

    assert record_id > 0
    assert repository.count() == 1


def test_upsert_updates_existing_opportunity(
    tmp_path,
):
    repository = OpportunityRepository(
        tmp_path / "test.db"
    )

    repository.upsert(
        build_opportunity(
            score=50.0,
        )
    )

    updated = build_opportunity(
        score=90.0,
    )

    updated["title"] = "Updated title"

    repository.upsert(updated)

    assert repository.count() == 1

    stored = (
        repository
        .get_by_source_and_external_id(
            source="github",
            external_id="123",
        )
    )

    assert stored is not None
    assert stored["title"] == "Updated title"
    assert (
        stored["opportunity_score"]
        == 90.0
    )


def test_repository_hydrates_json_fields(
    tmp_path,
):
    repository = OpportunityRepository(
        tmp_path / "test.db"
    )

    repository.upsert(
        build_opportunity()
    )

    stored = (
        repository
        .get_by_source_and_external_id(
            source="github",
            external_id="123",
        )
    )

    assert stored is not None

    assert stored["pain_categories"] == [
        "manual_work"
    ]

    assert stored["pain_signals"] == {
        "manual_work": ["manual"]
    }

    assert stored["metadata"] == {
        "repository": "example/test"
    }


def test_list_ranked_orders_by_score(
    tmp_path,
):
    repository = OpportunityRepository(
        tmp_path / "test.db"
    )

    repository.upsert(
        build_opportunity(
            external_id="low",
            score=30.0,
        )
    )

    repository.upsert(
        build_opportunity(
            external_id="high",
            score=90.0,
        )
    )

    results = repository.list_ranked()

    assert len(results) == 2

    assert (
        results[0]["external_id"]
        == "high"
    )


def test_list_ranked_filters_minimum_score(
    tmp_path,
):
    repository = OpportunityRepository(
        tmp_path / "test.db"
    )

    repository.upsert(
        build_opportunity(
            external_id="low",
            score=30.0,
        )
    )

    repository.upsert(
        build_opportunity(
            external_id="high",
            score=90.0,
        )
    )

    results = repository.list_ranked(
        minimum_score=60.0
    )

    assert len(results) == 1

    assert (
        results[0]["external_id"]
        == "high"
    )


def test_upsert_many(tmp_path):
    repository = OpportunityRepository(
        tmp_path / "test.db"
    )

    count = repository.upsert_many(
        [
            build_opportunity("1"),
            build_opportunity("2"),
            build_opportunity("3"),
        ]
    )

    assert count == 3
    assert repository.count() == 3


def test_collection_run_repository(
    tmp_path,
):
    repository = CollectionRunRepository(
        tmp_path / "test.db"
    )

    run_id = repository.create(
        query="automation",
        limit_per_source=10,
        collected_count=100,
        pain_count=20,
        opportunity_count=10,
        persisted_count=10,
        collection_errors={
            "producthunt": "Unauthorized",
        },
        started_at=(
            "2026-07-26T10:00:00Z"
        ),
        finished_at=(
            "2026-07-26T10:01:00Z"
        ),
        execution_status="PARTIAL_SUCCESS",
    )

    assert run_id > 0

    runs = repository.list_recent()

    assert len(runs) == 1

    assert runs[0]["query"] == "automation"

    assert runs[0]["collection_errors"] == {
        "producthunt": "Unauthorized"
    }
