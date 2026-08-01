from __future__ import annotations

import sqlite3
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def _create_operational_database(path: Path) -> None:
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
                pain_categories TEXT,
                created_at TEXT
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
                duplicate_matches INTEGER,
                started_at TEXT,
                finished_at TEXT
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
            INSERT INTO opportunities (
                id, source, title, url, total_score, score_level,
                pain_categories, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "stack_overflow",
                "How do I get Google forms edit url to work",
                "https://stackoverflow.com/questions/example",
                78.0,
                "high",
                "manual_work | integration",
                "2026-07-31T12:00:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO query_expansion_runs (
                id, original_query, status, variation_count,
                successful_variations, failed_variations, total_matches,
                unique_opportunities, duplicate_matches, started_at, finished_at
            ) VALUES (1, ?, 'SUCCESS', 1, 1, 0, 1, 1, 0, ?, ?)
            """,
            (
                "google forms automation",
                "2026-07-31T12:00:00Z",
                "2026-07-31T12:01:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO opportunity_query_matches (
                id, expansion_run_id, variation_id, opportunity_id,
                opportunity_url, source, title, original_query,
                matched_query, first_seen_at
            ) VALUES (1, 1, 1, '1', ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://stackoverflow.com/questions/example",
                "stack_overflow",
                "How do I get Google forms edit url to work",
                "google forms automation",
                "google forms automation",
                "2026-07-31T12:00:00Z",
            ),
        )


def _button_by_label(app: AppTest, label: str):
    return next(button for button in app.button if button.label == label)


def test_clicking_analyze_opens_the_selected_opportunity(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _create_operational_database(data_dir / "radar.db")
    monkeypatch.setenv("OPPORTUNITY_RADAR_DATA_DIR", str(data_dir))

    app = AppTest.from_file(str(ROOT / "src/dashboard/app.py"), default_timeout=15)
    app.run()

    assert not app.exception
    assert app.session_state["primary_view"] == "1. Radar"
    _button_by_label(app, "Analisar oportunidade").click().run()

    assert not app.exception
    assert app.session_state["primary_view"] == "2. Oportunidade"
    assert any(header.value == "Entenda a oportunidade" for header in app.header)
    assert any(
        "How do I get Google forms edit url to work" in markdown.value
        for markdown in app.markdown
    )


def test_clicking_validation_preserves_selection_and_changes_step(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _create_operational_database(data_dir / "radar.db")
    monkeypatch.setenv("OPPORTUNITY_RADAR_DATA_DIR", str(data_dir))

    app = AppTest.from_file(str(ROOT / "src/dashboard/app.py"), default_timeout=15)
    app.run()
    _button_by_label(app, "Começar validação").click().run()

    assert not app.exception
    assert app.session_state["primary_view"] == "3. Validação"
    assert app.session_state["selected_opportunity_key"]
    assert any(header.value == "Valide antes de construir" for header in app.header)
