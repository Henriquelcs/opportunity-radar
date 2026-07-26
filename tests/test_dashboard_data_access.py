from __future__ import annotations

import sqlite3
from pathlib import Path

from src.dashboard.data_access import discover_databases, load_radar_data


def create_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE opportunities (
                id INTEGER PRIMARY KEY,
                source TEXT,
                title TEXT,
                url TEXT UNIQUE,
                total_score REAL,
                score_level TEXT,
                pain_categories TEXT
            );

            CREATE TABLE query_expansion_runs (
                id INTEGER PRIMARY KEY,
                original_query TEXT,
                status TEXT,
                variation_count INTEGER,
                successful_variations INTEGER,
                failed_variations INTEGER,
                total_matches INTEGER,
                unique_opportunities INTEGER,
                duplicate_matches INTEGER
            );

            CREATE TABLE query_expansion_variations (
                id INTEGER PRIMARY KEY,
                expansion_run_id INTEGER,
                position INTEGER,
                query TEXT,
                is_original INTEGER,
                status TEXT,
                pipeline_status TEXT,
                attempt_count INTEGER,
                collected_matches INTEGER,
                new_opportunities INTEGER,
                error_message TEXT
            );

            CREATE TABLE opportunity_query_matches (
                id INTEGER PRIMARY KEY,
                expansion_run_id INTEGER,
                variation_id INTEGER,
                opportunity_id TEXT,
                opportunity_url TEXT,
                source TEXT,
                title TEXT,
                original_query TEXT,
                matched_query TEXT,
                first_seen_at TEXT
            );
            """
        )
        connection.execute(
            """
            INSERT INTO opportunities
                (id, source, title, url, total_score, score_level, pain_categories)
            VALUES
                (1, 'github', 'Automate spreadsheet workflow',
                 'https://example.com/1', 62.5, 'medium', 'manual_work')
            """
        )
        connection.execute(
            """
            INSERT INTO query_expansion_runs
                (id, original_query, status, variation_count,
                 successful_variations, failed_variations, total_matches,
                 unique_opportunities, duplicate_matches)
            VALUES (1, 'spreadsheet automation', 'SUCCESS', 5, 5, 0, 2, 1, 1)
            """
        )
        connection.executemany(
            """
            INSERT INTO opportunity_query_matches
                (id, expansion_run_id, variation_id, opportunity_id,
                 opportunity_url, source, title, original_query,
                 matched_query, first_seen_at)
            VALUES (?, 1, ?, '1', 'https://example.com/1', 'github',
                    'Automate spreadsheet workflow', 'spreadsheet automation',
                    ?, '2026-07-26T12:00:00Z')
            """,
            [
                (1, 1, "Excel automation"),
                (2, 2, "Google Sheets automation"),
            ],
        )


def test_discover_databases_and_load_dashboard_dataset(tmp_path: Path) -> None:
    database = tmp_path / "radar.db"
    create_database(database)

    assert discover_databases(tmp_path) == [database]

    dataset = load_radar_data(tmp_path)

    assert len(dataset.databases) == 1
    assert len(dataset.opportunities) == 1
    opportunity = dataset.opportunities.iloc[0]
    assert opportunity["score"] == 62.5
    assert opportunity["level"] == "medium"
    assert opportunity["original_queries"] == "spreadsheet automation"
    assert opportunity["matched_queries"] == (
        "Excel automation | Google Sheets automation"
    )
    assert opportunity["match_count"] == 2
    assert len(dataset.expansion_runs) == 1
    assert len(dataset.matches) == 2


def test_selected_database_filter(tmp_path: Path) -> None:
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    create_database(first)
    create_database(second)

    dataset = load_radar_data(tmp_path, selected_database_files=["second.db"])

    assert dataset.databases["database_file"].tolist() == ["second.db"]
    assert dataset.opportunities["database_file"].unique().tolist() == ["second.db"]
