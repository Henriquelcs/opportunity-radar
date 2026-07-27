from __future__ import annotations

import sqlite3
from pathlib import Path

from src.cache.source_cache import SourceCache
from src.collectors.resilient import (
    RateLimitError,
    SnapshotSynchronizer,
)
from src.operations.runner_v2 import OpportunityRadarRunnerV2, RunnerV2Database


def opportunity_item(source: str, external_id: str) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "title": "Manual repetitive data entry workflow",
        "description": (
            "This manual data entry process is repetitive and takes hours. "
            "We need automation."
        ),
        "url": f"https://example.com/{source}/{external_id}",
        "author": "tester",
        "published_at": "2026-07-25T12:00:00+00:00",
        "tags": ["automation", "workflow"],
        "engagement": 10,
        "metadata": {},
    }


class CountingCollector:
    def __init__(
        self,
        source: str,
        *,
        items: list[dict] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.source = source
        self.items = items or []
        self.error = error
        self.calls = 0

    def collect(self, *, limit: int, since: str | None = None) -> list[dict]:
        del limit, since
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.items)


def table_count(database: Path, table: str) -> int:
    with sqlite3.connect(database) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_dev_is_called_once_for_multiple_queries(tmp_path) -> None:
    cache = SourceCache(tmp_path / "cache.db")
    dev = CountingCollector(
        "devto",
        items=[opportunity_item("devto", "1")],
    )
    sync = SnapshotSynchronizer(cache, [dev])
    database = tmp_path / "radar.db"
    runner = OpportunityRadarRunnerV2(
        database_path=database,
        cache_database_path=cache.database_path,
        synchronizer=sync,
    )

    result = runner.run(
        queries=(
            "repetitive data entry",
            "spreadsheet automation",
            "customer support automation",
        ),
        limit_per_source=10,
        minimum_score=20,
    )

    assert dev.calls == 1
    assert result.query_count == 3
    assert result.variation_count == 15
    assert table_count(database, "query_expansion_runs") == 3


def test_rate_limit_uses_old_cache(tmp_path) -> None:
    cache = SourceCache(tmp_path / "cache.db")
    cache.save_snapshot(
        "devto",
        [opportunity_item("devto", "cached")],
        status="LIVE",
    )
    dev = CountingCollector(
        "devto",
        error=RateLimitError("HTTP 429", retry_after_seconds=120),
    )
    sync = SnapshotSynchronizer(cache, [dev])

    result = sync.sync(limit_per_source=10)

    assert result.status == "DEGRADED"
    assert result.sources["devto"].status == "CACHE"
    assert result.items[0]["external_id"] == "cached"
    assert cache.cooldown_remaining("devto") > 0


def test_source_failure_generates_degraded_operation(tmp_path) -> None:
    cache = SourceCache(tmp_path / "cache.db")
    github = CountingCollector(
        "github",
        items=[opportunity_item("github", "1")],
    )
    dev = CountingCollector(
        "devto",
        error=RuntimeError("temporarily unavailable"),
    )
    sync = SnapshotSynchronizer(cache, [github, dev])
    database = tmp_path / "radar.db"
    runner = OpportunityRadarRunnerV2(
        database_path=database,
        cache_database_path=cache.database_path,
        synchronizer=sync,
    )

    result = runner.run(
        queries=("repetitive data entry",),
        limit_per_source=10,
        minimum_score=20,
    )

    assert result.status == "DEGRADED"
    assert result.source_statuses == {
        "github": "LIVE",
        "devto": "UNAVAILABLE",
    }
    assert table_count(database, "collection_runs") == 1
    with sqlite3.connect(database) as connection:
        status = connection.execute(
            "SELECT execution_status FROM collection_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    assert status == "PARTIAL_SUCCESS"

def create_expansion_schema(
    database: Path,
    *,
    include_database_path: bool,
    include_error_message: bool = True,
) -> None:
    database_path_column = (
        "database_path TEXT NOT NULL,"
        if include_database_path
        else ""
    )
    error_message_column = (
        "error_message TEXT NOT NULL DEFAULT '',"
        if include_error_message
        else ""
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"""
            CREATE TABLE query_expansion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_query TEXT NOT NULL,
                {database_path_column}
                status TEXT NOT NULL,
                variation_count INTEGER NOT NULL DEFAULT 0,
                successful_variations INTEGER NOT NULL DEFAULT 0,
                failed_variations INTEGER NOT NULL DEFAULT 0,
                unique_opportunities INTEGER NOT NULL DEFAULT 0,
                total_matches INTEGER NOT NULL DEFAULT 0,
                duplicate_matches INTEGER NOT NULL DEFAULT 0,
                {error_message_column}
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL
            )
            """
        )


def test_existing_operational_schema_receives_database_path(tmp_path) -> None:
    database_path = tmp_path / "existing_operational.db"
    create_expansion_schema(
        database_path,
        include_database_path=True,
    )
    database = RunnerV2Database(database_path)

    run_id = database.create_expansion_run(
        "repetitive data entry",
        status="RUNNING",
        variation_count=5,
        started_at="2026-07-26T12:00:00+00:00",
    )

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT database_path
            FROM query_expansion_runs
            WHERE id=?
            """,
            (run_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == str(database_path.resolve())


def test_pre_migration_database_is_upgraded_without_data_loss(tmp_path) -> None:
    database_path = tmp_path / "pre_migration.db"
    create_expansion_schema(
        database_path,
        include_database_path=False,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO query_expansion_runs (
                original_query, status, variation_count,
                started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "existing query",
                "SUCCESS",
                5,
                "2026-07-25T12:00:00+00:00",
                "2026-07-25T12:01:00+00:00",
            ),
        )

    database = RunnerV2Database(database_path)
    database.create_expansion_run(
        "new query",
        status="RUNNING",
        variation_count=5,
        started_at="2026-07-26T12:00:00+00:00",
    )

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(query_expansion_runs)"
            ).fetchall()
        }
        rows = connection.execute(
            """
            SELECT original_query, database_path
            FROM query_expansion_runs
            ORDER BY id
            """
        ).fetchall()
    assert "database_path" in columns
    assert rows == [
        ("existing query", str(database_path.resolve())),
        ("new query", str(database_path.resolve())),
    ]

def test_observed_legacy_schema_missing_error_message_completes_run(
    tmp_path,
) -> None:
    database_path = tmp_path / "observed_legacy_operational.db"
    create_expansion_schema(
        database_path,
        include_database_path=True,
        include_error_message=False,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO query_expansion_runs (
                original_query, database_path, status, variation_count,
                successful_variations, failed_variations,
                unique_opportunities, total_matches, duplicate_matches,
                started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy query",
                str(database_path.resolve()),
                "SUCCESS",
                5,
                5,
                0,
                1,
                5,
                4,
                "2026-07-25T12:00:00+00:00",
                "2026-07-25T12:01:00+00:00",
            ),
        )

    cache = SourceCache(tmp_path / "cache.db")
    github = CountingCollector(
        "github",
        items=[opportunity_item("github", "legacy-regression")],
    )
    runner = OpportunityRadarRunnerV2(
        database_path=database_path,
        cache_database_path=cache.database_path,
        synchronizer=SnapshotSynchronizer(cache, [github]),
    )

    result = runner.run(
        queries=("repetitive data entry",),
        limit_per_source=5,
        minimum_score=20,
    )

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(query_expansion_runs)"
            ).fetchall()
        }
        rows = connection.execute(
            """
            SELECT original_query, database_path, status, error_message
            FROM query_expansion_runs
            ORDER BY id
            """
        ).fetchall()

    assert result.status == "SUCCESS"
    assert "error_message" in columns
    assert rows[0] == (
        "legacy query",
        str(database_path.resolve()),
        "SUCCESS",
        "",
    )
    assert rows[-1][0] == "repetitive data entry"
    assert rows[-1][1] == str(database_path.resolve())
    assert rows[-1][2] == "SUCCESS"
    assert rows[-1][3] == ""


def test_runner_v2_schema_contract_is_complete(tmp_path) -> None:
    database = RunnerV2Database(tmp_path / "schema_contract.db")

    with database.connect() as connection:
        for table, required in database.REQUIRED_COLUMNS.items():
            actual = {
                row["name"]
                for row in connection.execute(
                    f'PRAGMA table_info("{table}")'
                ).fetchall()
            }
            assert set(required).issubset(actual)
