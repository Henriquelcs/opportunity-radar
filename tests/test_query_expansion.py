from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from src.query_expansion.query_expander import QueryExpander
from src.query_expansion.runner import QueryExpansionRunner


def test_curated_repetitive_data_entry_variations_are_exact() -> None:
    queries = [
        variation.query
        for variation in QueryExpander().expand("repetitive data entry")
    ]
    assert queries == [
        "repetitive data entry",
        "manual data entry",
        "data entry automation",
        "repetitive form filling",
        "manual record entry",
    ]


def test_curated_spreadsheet_variations_are_exact() -> None:
    queries = [
        variation.query
        for variation in QueryExpander().expand("spreadsheet automation")
    ]
    assert queries == [
        "spreadsheet automation",
        "Excel automation",
        "Google Sheets automation",
        "spreadsheet workflow",
        "spreadsheet data synchronization",
    ]


def test_curated_customer_support_variations_are_exact() -> None:
    queries = [
        variation.query
        for variation in QueryExpander().expand("customer support automation")
    ]
    assert queries == [
        "customer support automation",
        "helpdesk automation",
        "support ticket automation",
        "customer service workflow",
        "automated customer support",
    ]


def test_expansion_is_deterministic_unique_and_preserves_original() -> None:
    expander = QueryExpander()
    first = expander.expand("  invoice automation  ")
    second = expander.expand("invoice automation")

    assert first == second
    assert first[0].query == "invoice automation"
    assert first[0].is_original is True
    assert all(not item.is_original for item in first[1:])
    assert len({item.query.casefold() for item in first}) == len(first)
    assert len(first) == 5


def test_output_parser_extracts_source_title_and_url() -> None:
    output = """
    Fonte: github
    Título: Configure Google Sheets writeback credentials
    URL: https://github.com/example/repo/issues/1
    """
    parsed = QueryExpansionRunner._parse_opportunities(output)

    item = parsed["https://github.com/example/repo/issues/1"]
    assert item.source == "github"
    assert item.title == "Configure Google Sheets writeback credentials"


def test_runner_executes_all_variations_and_tracks_deduplication(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text("print('placeholder')\n", encoding="utf-8")
    database_path = tmp_path / "radar.db"

    def fake_executor(command, **kwargs):
        query = command[command.index("--query") + 1]
        db_path = Path(command[command.index("--database") + 1])
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO opportunities (source, title, url)
                VALUES ('github', 'Shared opportunity', 'https://example.com/shared')
                """
            )
            if query == "manual data entry":
                connection.execute(
                    """
                    INSERT OR IGNORE INTO opportunities (source, title, url)
                    VALUES ('stackoverflow', 'Second opportunity', 'https://example.com/second')
                    """
                )

        stdout = (
            "Status: SUCCESS\n"
            "Fonte: github\n"
            "Título: Shared opportunity\n"
            "URL: https://example.com/shared\n"
        )
        if query == "manual data entry":
            stdout += (
                "Fonte: stackoverflow\n"
                "Título: Second opportunity\n"
                "URL: https://example.com/second\n"
            )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    runner = QueryExpansionRunner(
        project_dir=project_dir,
        database_path=database_path,
        executor=fake_executor,
        sleeper=lambda _seconds: None,
        verbose=False,
        inter_query_delay_seconds=0,
    )
    summary = runner.run("repetitive data entry", limit=5, top=10)

    assert summary.status == "SUCCESS"
    assert summary.variation_count == 5
    assert summary.successful_variations == 5
    assert summary.failed_variations == 0
    assert summary.unique_opportunities == 2
    assert summary.total_matches == 6
    assert summary.duplicate_matches == 4

    with sqlite3.connect(database_path) as connection:
        variations = connection.execute(
            "SELECT COUNT(*) FROM query_expansion_variations"
        ).fetchone()[0]
        matches = connection.execute(
            "SELECT COUNT(*) FROM opportunity_query_matches"
        ).fetchone()[0]
        original_queries = connection.execute(
            "SELECT DISTINCT original_query FROM opportunity_query_matches"
        ).fetchall()

    assert variations == 5
    assert matches == 6
    assert original_queries == [("repetitive data entry",)]



def test_runner_retries_partial_success_and_records_attempt_count(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        "print('placeholder')\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "retry.db"
    attempts: dict[str, int] = {}
    delays: list[float] = []

    def fake_executor(command, **kwargs):
        query = command[command.index("--query") + 1]
        db_path = Path(command[command.index("--database") + 1])
        attempts[query] = attempts.get(query, 0) + 1

        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO opportunities (source, title, url)
                VALUES ('github', 'Qualified result', 'https://example.com/result')
                """
            )

        if query == "repetitive data entry" and attempts[query] == 1:
            stdout = (
                "Status: PARTIAL_SUCCESS\n"
                "Fontes com erro:\n"
                "- github: API rate limit\n"
                "Fonte: stackoverflow\n"
                "Título: Qualified result\n"
                "URL: https://example.com/result\n"
            )
        else:
            stdout = (
                "Status: SUCCESS\n"
                "Fonte: github\n"
                "Título: Qualified result\n"
                "URL: https://example.com/result\n"
            )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    runner = QueryExpansionRunner(
        project_dir=project_dir,
        database_path=database_path,
        executor=fake_executor,
        sleeper=delays.append,
        verbose=False,
        max_attempts=3,
        retry_delay_seconds=2,
        inter_query_delay_seconds=0,
    )
    summary = runner.run("repetitive data entry", limit=5, top=10)

    assert summary.status == "SUCCESS"
    assert summary.successful_variations == 5
    assert attempts["repetitive data entry"] == 2
    assert delays == [2]

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT status, pipeline_status, attempt_count, error_message
            FROM query_expansion_variations
            WHERE position = 0
            """
        ).fetchone()

    assert row == ("SUCCESS", "SUCCESS", 2, None)


def test_runner_fails_after_retry_budget_is_exhausted(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        "print('placeholder')\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "failed.db"
    attempts = 0
    delays: list[float] = []

    def fake_executor(command, **kwargs):
        nonlocal attempts
        attempts += 1
        db_path = Path(command[command.index("--database") + 1])
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE
                )
                """
            )
        return subprocess.CompletedProcess(
            command,
            0,
            (
                "Status: PARTIAL_SUCCESS\n"
                "Fontes com erro:\n"
                "- github: temporary failure\n"
            ),
            "",
        )

    runner = QueryExpansionRunner(
        project_dir=project_dir,
        database_path=database_path,
        expander=QueryExpander(max_variations=1),
        executor=fake_executor,
        sleeper=delays.append,
        verbose=False,
        max_attempts=2,
        retry_delay_seconds=3,
        inter_query_delay_seconds=0,
    )
    summary = runner.run("customer support automation", limit=5, top=10)

    assert summary.status == "FAILED"
    assert summary.successful_variations == 0
    assert summary.failed_variations == 1
    assert attempts == 2
    assert delays == [3]

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT status, pipeline_status, attempt_count, error_message
            FROM query_expansion_variations
            WHERE position = 0
            """
        ).fetchone()

    assert row[0] == "PARTIAL_SUCCESS"
    assert row[1] == "PARTIAL_SUCCESS"
    assert row[2] == 2
    assert "temporary failure" in row[3]
