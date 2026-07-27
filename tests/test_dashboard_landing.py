from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.dashboard.data_access import load_radar_data
from src.dashboard.presentation import (
    build_landing_summary,
    rank_opportunities,
    source_status_overview,
)


def test_landing_summary_uses_only_latest_operational_cycle() -> None:
    source_rows = pd.DataFrame(
        [
            {
                "database_file": "opportunity_radar_operational.db",
                "cycle_id": "old-cycle",
                "source": "github",
                "status": "LIVE",
                "item_count": 10,
                "new_item_count": 10,
                "created_at": "2026-07-26T21:00:00Z",
            },
            *[
                {
                    "database_file": "opportunity_radar_operational.db",
                    "cycle_id": "latest-cycle",
                    "source": source,
                    "status": status,
                    "item_count": 30 if status == "LIVE" else 5,
                    "new_item_count": 30 if status == "LIVE" else 0,
                    "created_at": "2026-07-26T23:00:00Z",
                }
                for source, status in (
                    ("github", "LIVE"),
                    ("stackoverflow", "CACHE"),
                    ("softwarerecs", "CACHE"),
                    ("webapps", "CACHE"),
                    ("hackernews", "LIVE"),
                    ("devto", "LIVE"),
                )
            ],
        ]
    )
    expansion_runs = pd.DataFrame(
        [
            {
                "database_file": "opportunity_radar_operational.db",
                "id": 1,
                "status": "FAILED",
                "duplicate_matches": 999,
                "started_at": "2026-07-26T21:01:00Z",
            },
            *[
                {
                    "database_file": "opportunity_radar_operational.db",
                    "id": run_id,
                    "status": "PARTIAL_SUCCESS",
                    "duplicate_matches": duplicates,
                    "started_at": f"2026-07-26T23:0{run_id - 9}:00Z",
                    "finished_at": f"2026-07-26T23:0{run_id - 9}:30Z",
                }
                for run_id, duplicates in ((10, 32), (11, 24), (12, 40))
            ],
        ]
    )
    variations = pd.DataFrame(
        [
            {
                "database_file": "opportunity_radar_operational.db",
                "expansion_run_id": float(run_id),
                "status": "PARTIAL_SUCCESS",
            }
            for run_id in (10, 11, 12)
            for _ in range(5)
        ]
    )
    opportunities = pd.DataFrame(
        [
            {
                "source": source,
                "curation_status": "unreviewed",
            }
            for source in ("github", "github", "devto", "hackernews")
        ]
    )

    summary = build_landing_summary(
        opportunities,
        expansion_runs,
        variations,
        source_rows,
    )

    assert summary.operation_status == "DEGRADED"
    assert summary.cycle_id == "latest-cycle"
    assert summary.connected_sources == 6
    assert summary.live_sources == 3
    assert summary.cached_sources == 3
    assert summary.queries_completed == 3
    assert summary.queries_total == 3
    assert summary.variations_completed == 15
    assert summary.variations_total == 15
    assert summary.duplicates_removed == 96
    assert summary.opportunities == 4
    assert summary.opportunity_sources == 3
    assert summary.pending_review == 4

    overview = source_status_overview(source_rows)
    assert overview["Fonte"].tolist() == [
        "GitHub",
        "Stack Overflow",
        "Software Recommendations",
        "Web Applications",
        "Hacker News",
        "DEV Community",
    ]
    assert overview["Estado"].tolist().count("Atualizada") == 3
    assert overview["Estado"].tolist().count("Cache reutilizado") == 3


def test_rank_opportunities_excludes_false_positive_and_deduplicates_title() -> None:
    frame = pd.DataFrame(
        [
            {
                "title": "Automate spreadsheet workflow",
                "url": "https://example.com/high",
                "source": "github",
                "score": 82,
                "match_count": 4,
                "curation_status": "review",
            },
            {
                "title": "  automate   spreadsheet workflow ",
                "url": "https://example.com/duplicate",
                "source": "devto",
                "score": 70,
                "match_count": 8,
                "curation_status": "unreviewed",
            },
            {
                "title": "Customer support assistant",
                "url": "https://example.com/false-positive",
                "source": "github",
                "score": 99,
                "match_count": 10,
                "curation_status": "false_positive",
            },
            {
                "title": "Form intake automation",
                "url": "https://example.com/form",
                "source": "webapps",
                "score": 74,
                "match_count": 3,
                "curation_status": "valid",
            },
        ]
    )

    ranked = rank_opportunities(frame, limit=6)

    assert ranked["url"].tolist() == [
        "https://example.com/high",
        "https://example.com/form",
    ]


def test_data_access_loads_source_sync_runs(tmp_path: Path) -> None:
    database = tmp_path / "opportunity_radar_operational.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE source_sync_runs (
                id INTEGER PRIMARY KEY,
                cycle_id TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                item_count INTEGER NOT NULL,
                new_item_count INTEGER NOT NULL,
                snapshot_at TEXT,
                retry_after_seconds INTEGER,
                error_message TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO source_sync_runs (
                cycle_id, source, status, item_count, new_item_count,
                snapshot_at, retry_after_seconds, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cycle-1",
                "github",
                "LIVE",
                30,
                30,
                "2026-07-26T23:00:00Z",
                0,
                "",
                "2026-07-26T23:00:00Z",
            ),
        )

    dataset = load_radar_data(tmp_path)

    assert len(dataset.source_sync_runs) == 1
    row = dataset.source_sync_runs.iloc[0]
    assert row["cycle_id"] == "cycle-1"
    assert row["source"] == "github"
    assert row["database_file"] == "opportunity_radar_operational.db"


def test_app_contains_income_landing_and_preserves_internal_areas() -> None:
    app_path = Path(__file__).resolve().parents[1] / "src/dashboard/app.py"
    content = app_path.read_text(encoding="utf-8")

    assert "Encontre dores reais." in content
    assert "Transforme-as em <span>renda extra.</span>" in content
    assert "Melhores oportunidades para validar agora" in content
    assert '"Início"' in content
    assert '"Análise"' in content
    assert '"Oportunidades"' in content
    assert '"Curadoria"' in content
    assert '"Consultas"' in content
    assert '"Execuções"' in content
    assert '"Área técnica"' in content
    assert "Consultas no último ciclo" in content
    assert "Expansões concluídas" not in content
