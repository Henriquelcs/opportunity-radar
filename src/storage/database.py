from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator


DEFAULT_DATABASE_PATH = Path(
    "data/opportunity_radar.db"
)


class Database:
    """
    Gerencia conexão e estrutura do banco SQLite.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_DATABASE_PATH
        ),
    ) -> None:
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def connect(self) -> sqlite3.Connection:
        """
        Cria uma conexão configurada com SQLite.
        """
        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        return connection

    def initialize(self) -> None:
        """
        Cria as tabelas e índices necessários.
        """
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    external_id TEXT NOT NULL,
                    source TEXT NOT NULL,

                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    author TEXT,
                    published_at TEXT,

                    pain_categories_json TEXT NOT NULL
                        DEFAULT '[]',

                    pain_signals_json TEXT NOT NULL
                        DEFAULT '{}',

                    metadata_json TEXT NOT NULL
                        DEFAULT '{}',

                    pain_score REAL NOT NULL DEFAULT 0,
                    urgency_score REAL NOT NULL DEFAULT 0,
                    engagement_score REAL NOT NULL DEFAULT 0,
                    market_score REAL NOT NULL DEFAULT 0,
                    confidence_score REAL NOT NULL DEFAULT 0,
                    opportunity_score REAL NOT NULL DEFAULT 0,

                    opportunity_level TEXT NOT NULL
                        DEFAULT 'very_low',

                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    UNIQUE(source, external_id)
                );

                CREATE INDEX IF NOT EXISTS
                    idx_opportunities_score
                ON opportunities(
                    opportunity_score DESC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_opportunities_source
                ON opportunities(source);

                CREATE INDEX IF NOT EXISTS
                    idx_opportunities_level
                ON opportunities(
                    opportunity_level
                );

                CREATE INDEX IF NOT EXISTS
                    idx_opportunities_last_seen
                ON opportunities(
                    last_seen_at DESC
                );

                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    query TEXT NOT NULL,
                    limit_per_source INTEGER NOT NULL,

                    collected_count INTEGER NOT NULL
                        DEFAULT 0,

                    pain_count INTEGER NOT NULL
                        DEFAULT 0,

                    opportunity_count INTEGER NOT NULL
                        DEFAULT 0,

                    persisted_count INTEGER NOT NULL
                        DEFAULT 0,

                    collection_errors_json TEXT NOT NULL
                        DEFAULT '{}',

                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    execution_status TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_collection_runs_started_at
                ON collection_runs(
                    started_at DESC
                );
                """
            )


def iter_rows(
    cursor: sqlite3.Cursor,
) -> Iterator[dict]:
    """
    Converte linhas SQLite em dicionários.
    """
    for row in cursor.fetchall():
        yield dict(row)
