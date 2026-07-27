from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.cache.source_cache import SourceCache, utc_iso
from src.collectors.resilient import (
    SnapshotSyncResult,
    SnapshotSynchronizer,
    build_default_collectors,
)


DEFAULT_QUERIES = (
    "repetitive data entry",
    "spreadsheet automation",
    "customer support automation",
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "using",
    "use",
    "need",
    "want",
    "help",
}

PAIN_PATTERNS: dict[str, tuple[str, ...]] = {
    "manual_work": (
        "manual",
        "manually",
        "data entry",
        "copy paste",
        "copy-paste",
        "spreadsheet",
        "excel",
        "csv",
    ),
    "repetition": (
        "repetitive",
        "repeated",
        "every day",
        "every week",
        "again and again",
        "duplicate work",
    ),
    "time_cost": (
        "time consuming",
        "time-consuming",
        "takes hours",
        "too slow",
        "slow process",
        "waste time",
        "tedious",
    ),
    "workflow_gap": (
        "workaround",
        "workflow",
        "multiple tools",
        "multiple steps",
        "too many clicks",
        "integration",
        "sync",
    ),
    "support_load": (
        "customer support",
        "support ticket",
        "tickets",
        "answering questions",
        "faq",
        "help desk",
        "helpdesk",
    ),
    "automation_demand": (
        "automate",
        "automation",
        "script",
        "bot",
        "api",
        "webhook",
        "no-code",
        "nocode",
    ),
    "failure_or_blocker": (
        "error",
        "issue",
        "problem",
        "fails",
        "failed",
        "broken",
        "cannot",
        "can't",
        "unable",
        "blocked",
    ),
}


@dataclass(frozen=True)
class OpportunityCandidate:
    item: dict[str, Any]
    matched_query: str
    original_query: str
    pain_categories: list[str]
    pain_signals: dict[str, list[str]]
    pain_score: float
    relevance_score: float
    engagement_score: float
    market_score: float
    confidence_score: float
    opportunity_score: float
    opportunity_level: str


@dataclass(frozen=True)
class RunnerV2Result:
    status: str
    database_path: str
    cache_database_path: str
    query_count: int
    variation_count: int
    source_statuses: dict[str, str]
    synchronized_items: int
    unique_opportunities: int
    total_matches: int
    collection_errors: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tokenize(value: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9+#.-]{1,}", value.casefold())
        if token not in STOPWORDS and len(token) > 1
    }
    return tokens


def expand_query(query: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", query).strip()
    if not normalized:
        raise ValueError("Consulta não pode ser vazia")
    variations = [
        normalized,
        f"{normalized} manual workflow",
        f"{normalized} repetitive task",
        f"{normalized} workaround",
        f"{normalized} automation tool",
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for variation in variations:
        key = variation.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(variation)
    return unique


def detect_pain(text: str) -> tuple[list[str], dict[str, list[str]]]:
    normalized = re.sub(r"\s+", " ", text.casefold())
    signals: dict[str, list[str]] = {}
    for category, patterns in PAIN_PATTERNS.items():
        matches = [pattern for pattern in patterns if pattern in normalized]
        if matches:
            signals[category] = matches
    return sorted(signals), signals


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def score_candidate(
    item: dict[str, Any],
    *,
    original_query: str,
    matched_query: str,
) -> OpportunityCandidate | None:
    title = str(item.get("title", "") or "")
    description = str(item.get("description", "") or "")
    tags = " ".join(str(tag) for tag in item.get("tags", []) or [])
    full_text = f"{title}\n{description}\n{tags}".strip()
    text_tokens = _tokenize(full_text)
    original_tokens = _tokenize(original_query)
    variation_tokens = _tokenize(matched_query)
    core_tokens = original_tokens or variation_tokens
    overlap = core_tokens.intersection(text_tokens)
    if not overlap:
        return None

    categories, signals = detect_pain(full_text)
    if not categories:
        return None

    overlap_ratio = len(overlap) / max(1, len(core_tokens))
    title_overlap = len(core_tokens.intersection(_tokenize(title)))
    pain_signal_count = sum(len(values) for values in signals.values())

    pain_score = min(30.0, 8.0 + pain_signal_count * 4.0)
    relevance_score = min(
        35.0,
        overlap_ratio * 25.0 + min(10.0, title_overlap * 5.0),
    )
    try:
        engagement = max(0.0, float(item.get("engagement", 0) or 0))
    except (TypeError, ValueError):
        engagement = 0.0
    engagement_score = min(15.0, math.log1p(engagement) * 3.5)

    published_at = _parse_datetime(item.get("published_at"))
    if published_at is None:
        freshness_score = 3.0
    else:
        age_days = max(
            0.0,
            (datetime.now(timezone.utc) - published_at).total_seconds() / 86400,
        )
        freshness_score = max(1.0, 10.0 - min(9.0, age_days / 10.0))

    market_score = min(
        10.0,
        2.0
        + (3.0 if "automation_demand" in categories else 0.0)
        + (2.0 if "manual_work" in categories else 0.0)
        + (2.0 if "support_load" in categories else 0.0)
        + (1.0 if "workflow_gap" in categories else 0.0),
    )
    confidence_score = min(
        10.0,
        3.0
        + overlap_ratio * 4.0
        + min(3.0, len(categories) * 0.75),
    )
    total = round(
        min(
            100.0,
            pain_score
            + relevance_score
            + engagement_score
            + freshness_score
            + market_score
            + confidence_score,
        ),
        2,
    )
    if total >= 75:
        level = "high"
    elif total >= 55:
        level = "medium"
    elif total >= 35:
        level = "low"
    else:
        level = "very_low"

    return OpportunityCandidate(
        item=item,
        matched_query=matched_query,
        original_query=original_query,
        pain_categories=categories,
        pain_signals=signals,
        pain_score=round(pain_score, 2),
        relevance_score=round(relevance_score, 2),
        engagement_score=round(engagement_score, 2),
        market_score=round(market_score, 2),
        confidence_score=round(confidence_score, 2),
        opportunity_score=total,
        opportunity_level=level,
    )


class RunnerV2Database:
    REQUIRED_COLUMNS: dict[str, dict[str, str]] = {
        "opportunities": {
            "external_id": "TEXT NOT NULL DEFAULT ''",
            "source": "TEXT NOT NULL DEFAULT ''",
            "title": "TEXT NOT NULL DEFAULT ''",
            "description": "TEXT NOT NULL DEFAULT ''",
            "url": "TEXT NOT NULL DEFAULT ''",
            "author": "TEXT",
            "published_at": "TEXT",
            "pain_categories_json": "TEXT NOT NULL DEFAULT '[]'",
            "pain_categories": "TEXT NOT NULL DEFAULT ''",
            "pain_signals_json": "TEXT NOT NULL DEFAULT '{}'",
            "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
            "pain_score": "REAL NOT NULL DEFAULT 0",
            "urgency_score": "REAL NOT NULL DEFAULT 0",
            "engagement_score": "REAL NOT NULL DEFAULT 0",
            "market_score": "REAL NOT NULL DEFAULT 0",
            "confidence_score": "REAL NOT NULL DEFAULT 0",
            "opportunity_score": "REAL NOT NULL DEFAULT 0",
            "opportunity_level": "TEXT NOT NULL DEFAULT 'very_low'",
            "first_seen_at": "TEXT NOT NULL DEFAULT ''",
            "last_seen_at": "TEXT NOT NULL DEFAULT ''",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        },
        "collection_runs": {
            "query": "TEXT NOT NULL DEFAULT ''",
            "limit_per_source": "INTEGER NOT NULL DEFAULT 0",
            "collected_count": "INTEGER NOT NULL DEFAULT 0",
            "pain_count": "INTEGER NOT NULL DEFAULT 0",
            "opportunity_count": "INTEGER NOT NULL DEFAULT 0",
            "persisted_count": "INTEGER NOT NULL DEFAULT 0",
            "collection_errors_json": "TEXT NOT NULL DEFAULT '{}'",
            "started_at": "TEXT NOT NULL DEFAULT ''",
            "finished_at": "TEXT NOT NULL DEFAULT ''",
            "execution_status": "TEXT NOT NULL DEFAULT ''",
        },
        "query_expansion_runs": {
            "original_query": "TEXT NOT NULL DEFAULT ''",
            "database_path": "TEXT NOT NULL DEFAULT ''",
            "status": "TEXT NOT NULL DEFAULT 'RUNNING'",
            "variation_count": "INTEGER NOT NULL DEFAULT 0",
            "successful_variations": "INTEGER NOT NULL DEFAULT 0",
            "failed_variations": "INTEGER NOT NULL DEFAULT 0",
            "unique_opportunities": "INTEGER NOT NULL DEFAULT 0",
            "total_matches": "INTEGER NOT NULL DEFAULT 0",
            "duplicate_matches": "INTEGER NOT NULL DEFAULT 0",
            "error_message": "TEXT NOT NULL DEFAULT ''",
            "started_at": "TEXT NOT NULL DEFAULT ''",
            "finished_at": "TEXT NOT NULL DEFAULT ''",
        },
        "query_expansion_variations": {
            "expansion_run_id": "INTEGER NOT NULL DEFAULT 0",
            "position": "INTEGER NOT NULL DEFAULT 0",
            "query": "TEXT NOT NULL DEFAULT ''",
            "is_original": "INTEGER NOT NULL DEFAULT 0",
            "status": "TEXT NOT NULL DEFAULT ''",
            "pipeline_status": "TEXT NOT NULL DEFAULT ''",
            "attempt_count": "INTEGER NOT NULL DEFAULT 1",
            "collected_matches": "INTEGER NOT NULL DEFAULT 0",
            "new_opportunities": "INTEGER NOT NULL DEFAULT 0",
            "error_message": "TEXT NOT NULL DEFAULT ''",
            "started_at": "TEXT NOT NULL DEFAULT ''",
            "finished_at": "TEXT NOT NULL DEFAULT ''",
        },
        "opportunity_query_matches": {
            "expansion_run_id": "INTEGER NOT NULL DEFAULT 0",
            "variation_id": "INTEGER NOT NULL DEFAULT 0",
            "opportunity_id": "TEXT NOT NULL DEFAULT ''",
            "opportunity_url": "TEXT NOT NULL DEFAULT ''",
            "source": "TEXT NOT NULL DEFAULT ''",
            "title": "TEXT NOT NULL DEFAULT ''",
            "original_query": "TEXT NOT NULL DEFAULT ''",
            "matched_query": "TEXT NOT NULL DEFAULT ''",
            "first_seen_at": "TEXT NOT NULL DEFAULT ''",
        },
        "source_sync_runs": {
            "cycle_id": "TEXT NOT NULL DEFAULT ''",
            "source": "TEXT NOT NULL DEFAULT ''",
            "status": "TEXT NOT NULL DEFAULT ''",
            "item_count": "INTEGER NOT NULL DEFAULT 0",
            "new_item_count": "INTEGER NOT NULL DEFAULT 0",
            "snapshot_at": "TEXT NOT NULL DEFAULT ''",
            "retry_after_seconds": "INTEGER NOT NULL DEFAULT 0",
            "error_message": "TEXT NOT NULL DEFAULT ''",
            "created_at": "TEXT NOT NULL DEFAULT ''",
        },
    }

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @staticmethod
    def _table_columns(
        connection: sqlite3.Connection,
        table: str,
    ) -> set[str]:
        return {
            str(row["name"])
            for row in connection.execute(
                f'PRAGMA table_info("{table}")'
            ).fetchall()
        }

    @classmethod
    def _migrate_required_columns(
        cls,
        connection: sqlite3.Connection,
    ) -> list[str]:
        applied: list[str] = []
        for table, required_columns in cls.REQUIRED_COLUMNS.items():
            existing = cls._table_columns(connection, table)
            if not existing:
                raise RuntimeError(
                    f"Tabela obrigatória ausente após inicialização: {table}"
                )
            for column, definition in required_columns.items():
                if column in existing:
                    continue
                connection.execute(
                    f'ALTER TABLE "{table}" '
                    f'ADD COLUMN "{column}" {definition}'
                )
                existing.add(column)
                applied.append(f"{table}.{column}")
        return applied

    @classmethod
    def _validate_required_columns(
        cls,
        connection: sqlite3.Connection,
    ) -> None:
        missing: list[str] = []
        for table, required_columns in cls.REQUIRED_COLUMNS.items():
            existing = cls._table_columns(connection, table)
            missing.extend(
                f"{table}.{column}"
                for column in required_columns
                if column not in existing
            )
        if missing:
            raise RuntimeError(
                "Schema Runner V2 incompatível após migração: "
                + ", ".join(missing)
            )

    def initialize(self) -> None:
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
                    pain_categories_json TEXT NOT NULL DEFAULT '[]',
                    pain_categories TEXT NOT NULL DEFAULT '',
                    pain_signals_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    pain_score REAL NOT NULL DEFAULT 0,
                    urgency_score REAL NOT NULL DEFAULT 0,
                    engagement_score REAL NOT NULL DEFAULT 0,
                    market_score REAL NOT NULL DEFAULT 0,
                    confidence_score REAL NOT NULL DEFAULT 0,
                    opportunity_score REAL NOT NULL DEFAULT 0,
                    opportunity_level TEXT NOT NULL DEFAULT 'very_low',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source, external_id)
                );

                CREATE INDEX IF NOT EXISTS idx_opportunities_score
                ON opportunities(opportunity_score DESC);

                CREATE INDEX IF NOT EXISTS idx_opportunities_source
                ON opportunities(source);

                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    limit_per_source INTEGER NOT NULL,
                    collected_count INTEGER NOT NULL DEFAULT 0,
                    pain_count INTEGER NOT NULL DEFAULT 0,
                    opportunity_count INTEGER NOT NULL DEFAULT 0,
                    persisted_count INTEGER NOT NULL DEFAULT 0,
                    collection_errors_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    execution_status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS query_expansion_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_query TEXT NOT NULL,
                    database_path TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    variation_count INTEGER NOT NULL DEFAULT 0,
                    successful_variations INTEGER NOT NULL DEFAULT 0,
                    failed_variations INTEGER NOT NULL DEFAULT 0,
                    unique_opportunities INTEGER NOT NULL DEFAULT 0,
                    total_matches INTEGER NOT NULL DEFAULT 0,
                    duplicate_matches INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS query_expansion_variations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expansion_run_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    is_original INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    pipeline_status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 1,
                    collected_matches INTEGER NOT NULL DEFAULT 0,
                    new_opportunities INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    FOREIGN KEY(expansion_run_id)
                        REFERENCES query_expansion_runs(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS opportunity_query_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expansion_run_id INTEGER NOT NULL,
                    variation_id INTEGER NOT NULL,
                    opportunity_id TEXT NOT NULL,
                    opportunity_url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    original_query TEXT NOT NULL,
                    matched_query TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    UNIQUE(
                        expansion_run_id,
                        variation_id,
                        opportunity_id,
                        matched_query
                    )
                );

                CREATE TABLE IF NOT EXISTS source_sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    new_item_count INTEGER NOT NULL DEFAULT 0,
                    snapshot_at TEXT NOT NULL,
                    retry_after_seconds INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_source_sync_runs_cycle
                ON source_sync_runs(cycle_id, source);
                """
            )
            applied = self._migrate_required_columns(connection)
            connection.execute(
                """
                UPDATE query_expansion_runs
                SET database_path=?
                WHERE database_path IS NULL OR TRIM(database_path)=''
                """,
                (str(self.database_path),),
            )
            self._validate_required_columns(connection)
            if applied:
                print(
                    "[DB] migração idempotente aplicada: "
                    + ", ".join(applied),
                    flush=True,
                )
            print("[DB] schema_runner_v2=OK", flush=True)

    def record_source_sync(
        self,
        cycle_id: str,
        sync: SnapshotSyncResult,
    ) -> None:
        timestamp = utc_iso()
        rows = [
            (
                cycle_id,
                source,
                state.status,
                state.item_count,
                state.new_item_count,
                state.snapshot_at,
                state.retry_after_seconds,
                state.error,
                timestamp,
            )
            for source, state in sync.sources.items()
        ]
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO source_sync_runs (
                    cycle_id, source, status, item_count, new_item_count,
                    snapshot_at, retry_after_seconds, error_message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def create_expansion_run(
        self,
        original_query: str,
        *,
        status: str,
        variation_count: int,
        started_at: str,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_expansion_runs (
                    original_query, database_path, status, variation_count,
                    started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    original_query,
                    str(self.database_path),
                    status,
                    variation_count,
                    started_at,
                    started_at,
                ),
            )
            return int(cursor.lastrowid)

    def create_variation(
        self,
        expansion_run_id: int,
        *,
        position: int,
        query: str,
        is_original: bool,
        status: str,
        error_message: str,
        started_at: str,
        finished_at: str,
        collected_matches: int,
        new_opportunities: int,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_expansion_variations (
                    expansion_run_id, position, query, is_original,
                    status, pipeline_status, attempt_count,
                    collected_matches, new_opportunities, error_message,
                    started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    expansion_run_id,
                    position,
                    query,
                    int(is_original),
                    status,
                    status,
                    collected_matches,
                    new_opportunities,
                    error_message,
                    started_at,
                    finished_at,
                ),
            )
            return int(cursor.lastrowid)

    def upsert_opportunity(
        self,
        candidate: OpportunityCandidate,
    ) -> int:
        item = candidate.item
        now = utc_iso()
        external_id = str(item.get("external_id", "") or "").strip()
        source = str(item.get("source", "") or "").strip()
        if not external_id or not source:
            raise ValueError("Oportunidade sem source/external_id")
        metadata = dict(item.get("metadata", {}) or {})
        metadata["matched_query"] = candidate.matched_query
        metadata["original_query"] = candidate.original_query
        metadata["relevance_score"] = candidate.relevance_score
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO opportunities (
                    external_id, source, title, description, url, author,
                    published_at, pain_categories_json, pain_categories,
                    pain_signals_json, metadata_json, pain_score,
                    urgency_score, engagement_score, market_score,
                    confidence_score, opportunity_score, opportunity_level,
                    first_seen_at, last_seen_at, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                ON CONFLICT(source, external_id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    url=excluded.url,
                    author=excluded.author,
                    published_at=excluded.published_at,
                    pain_categories_json=excluded.pain_categories_json,
                    pain_categories=excluded.pain_categories,
                    pain_signals_json=excluded.pain_signals_json,
                    metadata_json=excluded.metadata_json,
                    pain_score=MAX(
                        opportunities.pain_score,
                        excluded.pain_score
                    ),
                    engagement_score=MAX(
                        opportunities.engagement_score,
                        excluded.engagement_score
                    ),
                    market_score=MAX(
                        opportunities.market_score,
                        excluded.market_score
                    ),
                    confidence_score=MAX(
                        opportunities.confidence_score,
                        excluded.confidence_score
                    ),
                    opportunity_score=MAX(
                        opportunities.opportunity_score,
                        excluded.opportunity_score
                    ),
                    opportunity_level=CASE
                        WHEN excluded.opportunity_score
                             >= opportunities.opportunity_score
                        THEN excluded.opportunity_level
                        ELSE opportunities.opportunity_level
                    END,
                    last_seen_at=excluded.last_seen_at,
                    updated_at=excluded.updated_at
                """,
                (
                    external_id,
                    source,
                    str(item.get("title", "") or ""),
                    str(item.get("description", "") or ""),
                    str(item.get("url", "") or ""),
                    str(item.get("author", "") or ""),
                    str(item.get("published_at", "") or ""),
                    json.dumps(candidate.pain_categories, ensure_ascii=False),
                    " | ".join(candidate.pain_categories),
                    json.dumps(candidate.pain_signals, ensure_ascii=False),
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    candidate.pain_score,
                    candidate.engagement_score,
                    candidate.market_score,
                    candidate.confidence_score,
                    candidate.opportunity_score,
                    candidate.opportunity_level,
                    now,
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT id FROM opportunities
                WHERE source=? AND external_id=?
                """,
                (source, external_id),
            ).fetchone()
            return int(row["id"])

    def add_match(
        self,
        *,
        expansion_run_id: int,
        variation_id: int,
        opportunity_id: int,
        candidate: OpportunityCandidate,
    ) -> None:
        item = candidate.item
        identity = f"{item.get('source')}:{item.get('external_id')}"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO opportunity_query_matches (
                    expansion_run_id, variation_id, opportunity_id,
                    opportunity_url, source, title, original_query,
                    matched_query, first_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expansion_run_id,
                    variation_id,
                    identity or str(opportunity_id),
                    str(item.get("url", "") or ""),
                    str(item.get("source", "") or ""),
                    str(item.get("title", "") or ""),
                    candidate.original_query,
                    candidate.matched_query,
                    utc_iso(),
                ),
            )

    def finish_expansion_run(
        self,
        expansion_run_id: int,
        *,
        status: str,
        successful_variations: int,
        failed_variations: int,
        unique_opportunities: int,
        total_matches: int,
        duplicate_matches: int,
        error_message: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE query_expansion_runs
                SET status=?,
                    successful_variations=?,
                    failed_variations=?,
                    unique_opportunities=?,
                    total_matches=?,
                    duplicate_matches=?,
                    error_message=?,
                    finished_at=?
                WHERE id=?
                """,
                (
                    status,
                    successful_variations,
                    failed_variations,
                    unique_opportunities,
                    total_matches,
                    duplicate_matches,
                    error_message,
                    utc_iso(),
                    expansion_run_id,
                ),
            )

    def add_collection_run(
        self,
        *,
        query: str,
        limit_per_source: int,
        collected_count: int,
        pain_count: int,
        opportunity_count: int,
        persisted_count: int,
        collection_errors: dict[str, str],
        started_at: str,
        execution_status: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO collection_runs (
                    query, limit_per_source, collected_count, pain_count,
                    opportunity_count, persisted_count,
                    collection_errors_json, started_at, finished_at,
                    execution_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query,
                    limit_per_source,
                    collected_count,
                    pain_count,
                    opportunity_count,
                    persisted_count,
                    json.dumps(
                        collection_errors,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    started_at,
                    utc_iso(),
                    execution_status,
                ),
            )


class OpportunityRadarRunnerV2:
    def __init__(
        self,
        *,
        database_path: str | Path,
        cache_database_path: str | Path,
        synchronizer: SnapshotSynchronizer | None = None,
    ) -> None:
        self.database = RunnerV2Database(database_path)
        self.cache = SourceCache(cache_database_path)
        self.synchronizer = synchronizer or SnapshotSynchronizer(
            self.cache,
            build_default_collectors(self.cache),
        )

    @staticmethod
    def _error_summary(sync: SnapshotSyncResult) -> str:
        if not sync.errors:
            return ""
        return " | ".join(
            f"{source}: {message}"
            for source, message in sorted(sync.errors.items())
        )

    def run(
        self,
        *,
        queries: Iterable[str] = DEFAULT_QUERIES,
        limit_per_source: int = 30,
        minimum_score: float = 35.0,
    ) -> RunnerV2Result:
        normalized_queries = [
            re.sub(r"\s+", " ", str(query)).strip()
            for query in queries
            if str(query).strip()
        ]
        if not normalized_queries:
            raise ValueError("É necessário informar ao menos uma consulta")
        cycle_id = hashlib.sha1(
            (
                utc_iso()
                + "|"
                + "|".join(normalized_queries)
                + f"|{limit_per_source}"
            ).encode("utf-8")
        ).hexdigest()[:16]

        print("=" * 72)
        print("OPPORTUNITY RADAR — RUNNER V2")
        print(
            f"cycle_id={cycle_id} queries={len(normalized_queries)} "
            f"limit_per_source={limit_per_source}"
        )
        print("=" * 72)

        sync = self.synchronizer.sync(limit_per_source=limit_per_source)
        self.database.record_source_sync(cycle_id, sync)
        if sync.status == "FAILED":
            raise RuntimeError(
                "Todas as fontes estão indisponíveis e nenhum cache utilizável existe"
            )

        operation_unique: set[tuple[str, str]] = set()
        operation_match_count = 0
        variation_total = 0
        source_error_text = self._error_summary(sync)
        variation_status = (
            "SUCCESS" if sync.status == "SUCCESS" else "PARTIAL_SUCCESS"
        )

        for original_query in normalized_queries:
            started_at = utc_iso()
            variations = expand_query(original_query)
            variation_total += len(variations)
            expansion_run_id = self.database.create_expansion_run(
                original_query,
                status="RUNNING",
                variation_count=len(variations),
                started_at=started_at,
            )
            query_unique: set[tuple[str, str]] = set()
            query_matches = 0
            pain_item_count = 0
            print(
                f"[LOCAL] consulta={original_query!r} "
                f"variações={len(variations)} snapshot_itens={len(sync.items)}"
            )
            for position, variation in enumerate(variations, start=1):
                variation_started = utc_iso()
                candidates: list[OpportunityCandidate] = []
                for item in sync.items:
                    candidate = score_candidate(
                        item,
                        original_query=original_query,
                        matched_query=variation,
                    )
                    if candidate is None:
                        continue
                    pain_item_count += 1
                    if candidate.opportunity_score >= minimum_score:
                        candidates.append(candidate)

                new_in_variation = 0
                pending_rows: list[tuple[int, OpportunityCandidate]] = []
                for candidate in candidates:
                    item_key = (
                        str(candidate.item.get("source", "")),
                        str(candidate.item.get("external_id", "")),
                    )
                    if item_key not in query_unique:
                        query_unique.add(item_key)
                        new_in_variation += 1
                    operation_unique.add(item_key)
                    opportunity_id = self.database.upsert_opportunity(candidate)
                    pending_rows.append((opportunity_id, candidate))

                variation_id = self.database.create_variation(
                    expansion_run_id,
                    position=position,
                    query=variation,
                    is_original=position == 1,
                    status=variation_status,
                    error_message=source_error_text,
                    started_at=variation_started,
                    finished_at=utc_iso(),
                    collected_matches=len(candidates),
                    new_opportunities=new_in_variation,
                )
                for opportunity_id, candidate in pending_rows:
                    self.database.add_match(
                        expansion_run_id=expansion_run_id,
                        variation_id=variation_id,
                        opportunity_id=opportunity_id,
                        candidate=candidate,
                    )
                query_matches += len(candidates)
                operation_match_count += len(candidates)
                print(
                    f"[LOCAL] {position}/{len(variations)} "
                    f"status={variation_status} matches={len(candidates)} "
                    f"novas={new_in_variation} query={variation!r}"
                )

            duplicate_matches = max(0, query_matches - len(query_unique))
            run_status = (
                "SUCCESS" if sync.status == "SUCCESS" else "PARTIAL_SUCCESS"
            )
            self.database.finish_expansion_run(
                expansion_run_id,
                status=run_status,
                successful_variations=len(variations),
                failed_variations=0,
                unique_opportunities=len(query_unique),
                total_matches=query_matches,
                duplicate_matches=duplicate_matches,
                error_message=source_error_text,
            )
            self.database.add_collection_run(
                query=original_query,
                limit_per_source=limit_per_source,
                collected_count=len(sync.items),
                pain_count=pain_item_count,
                opportunity_count=len(query_unique),
                persisted_count=len(query_unique),
                collection_errors=sync.errors,
                started_at=started_at,
                execution_status=run_status,
            )
            print(
                f"[QUERY] status={run_status} únicas={len(query_unique)} "
                f"matches={query_matches} duplicadas={duplicate_matches}"
            )

        final_status = "SUCCESS" if sync.status == "SUCCESS" else "DEGRADED"
        result = RunnerV2Result(
            status=final_status,
            database_path=str(self.database.database_path),
            cache_database_path=str(self.cache.database_path),
            query_count=len(normalized_queries),
            variation_count=variation_total,
            source_statuses={
                source: state.status for source, state in sync.sources.items()
            },
            synchronized_items=len(sync.items),
            unique_opportunities=len(operation_unique),
            total_matches=operation_match_count,
            collection_errors=sync.errors,
        )
        print("[RESULT] " + json.dumps(result.to_dict(), ensure_ascii=False))
        return result
