from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    current = value or utc_now()
    return current.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


@dataclass(frozen=True)
class SourceSnapshot:
    id: int
    source: str
    snapshot_key: str
    fetched_at: str
    item_count: int
    status: str
    error: str
    items: list[dict[str, Any]]


class SourceCache:
    """Cache SQLite persistente para snapshots, itens e cooldowns de fontes."""

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

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    snapshot_key TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    UNIQUE(source, snapshot_key)
                );

                CREATE INDEX IF NOT EXISTS idx_source_snapshots_latest
                ON source_snapshots(source, fetched_at DESC, id DESC);

                CREATE TABLE IF NOT EXISTS source_items (
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(source, external_id)
                );

                CREATE INDEX IF NOT EXISTS idx_source_items_fetched
                ON source_items(source, fetched_at DESC);

                CREATE TABLE IF NOT EXISTS source_cooldowns (
                    source TEXT PRIMARY KEY,
                    blocked_until TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _clean_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "") or "").strip()
            external_id = str(item.get("external_id", "") or "").strip()
            if not source or not external_id:
                continue
            cleaned.append(dict(item))
        return cleaned

    def save_snapshot(
        self,
        source: str,
        items: Iterable[dict[str, Any]],
        *,
        status: str = "LIVE",
        error: str = "",
        snapshot_key: str | None = None,
        fetched_at: str | None = None,
    ) -> SourceSnapshot:
        source_name = source.strip()
        if not source_name:
            raise ValueError("source não pode ser vazio")
        timestamp = fetched_at or utc_iso()
        key = snapshot_key or timestamp
        payload = self._clean_items(items)
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO source_snapshots (
                    source, snapshot_key, fetched_at, item_count,
                    status, error, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, snapshot_key) DO UPDATE SET
                    fetched_at=excluded.fetched_at,
                    item_count=excluded.item_count,
                    status=excluded.status,
                    error=excluded.error,
                    payload_json=excluded.payload_json
                """,
                (
                    source_name,
                    key,
                    timestamp,
                    len(payload),
                    status,
                    error,
                    payload_json,
                ),
            )
            row_id = int(cursor.lastrowid or 0)
            if row_id == 0:
                row = connection.execute(
                    """
                    SELECT id FROM source_snapshots
                    WHERE source=? AND snapshot_key=?
                    """,
                    (source_name, key),
                ).fetchone()
                row_id = int(row["id"])
        return SourceSnapshot(
            id=row_id,
            source=source_name,
            snapshot_key=key,
            fetched_at=timestamp,
            item_count=len(payload),
            status=status,
            error=error,
            items=payload,
        )

    def latest_snapshot(
        self,
        source: str,
        *,
        require_items: bool = False,
    ) -> SourceSnapshot | None:
        where = "source=?"
        parameters: list[Any] = [source]
        if require_items:
            where += " AND item_count > 0"
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT id, source, snapshot_key, fetched_at, item_count,
                       status, error, payload_json
                FROM source_snapshots
                WHERE {where}
                ORDER BY fetched_at DESC, id DESC
                LIMIT 1
                """,
                parameters,
            ).fetchone()
        if row is None:
            return None
        return SourceSnapshot(
            id=int(row["id"]),
            source=str(row["source"]),
            snapshot_key=str(row["snapshot_key"]),
            fetched_at=str(row["fetched_at"]),
            item_count=int(row["item_count"]),
            status=str(row["status"]),
            error=str(row["error"]),
            items=json.loads(str(row["payload_json"])),
        )

    def upsert_items(
        self,
        source: str,
        items: Iterable[dict[str, Any]],
        *,
        fetched_at: str | None = None,
    ) -> int:
        timestamp = fetched_at or utc_iso()
        payload = self._clean_items(items)
        rows = [
            (
                source,
                str(item["external_id"]),
                timestamp,
                json.dumps(item, ensure_ascii=False, sort_keys=True),
            )
            for item in payload
        ]
        if not rows:
            return 0
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO source_items (
                    source, external_id, fetched_at, payload_json
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    fetched_at=excluded.fetched_at,
                    payload_json=excluded.payload_json
                """,
                rows,
            )
        return len(rows)

    def get_item(
        self,
        source: str,
        external_id: str,
        *,
        max_age_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT fetched_at, payload_json
                FROM source_items
                WHERE source=? AND external_id=?
                """,
                (source, str(external_id)),
            ).fetchone()
        if row is None:
            return None
        if max_age_seconds is not None:
            age = utc_now() - parse_utc(str(row["fetched_at"]))
            if age > timedelta(seconds=max_age_seconds):
                return None
        return json.loads(str(row["payload_json"]))

    def set_cooldown(
        self,
        source: str,
        retry_after_seconds: int,
        *,
        reason: str = "",
    ) -> str:
        seconds = max(1, int(retry_after_seconds))
        blocked_until = utc_iso(utc_now() + timedelta(seconds=seconds))
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_cooldowns (
                    source, blocked_until, reason, updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    blocked_until=excluded.blocked_until,
                    reason=excluded.reason,
                    updated_at=excluded.updated_at
                """,
                (source, blocked_until, reason, utc_iso()),
            )
        return blocked_until

    def cooldown_remaining(self, source: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT blocked_until
                FROM source_cooldowns
                WHERE source=?
                """,
                (source,),
            ).fetchone()
        if row is None:
            return 0
        remaining = parse_utc(str(row["blocked_until"])) - utc_now()
        return max(0, int(remaining.total_seconds()))

    def clear_cooldown(self, source: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM source_cooldowns WHERE source=?",
                (source,),
            )

    def inventory(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT source, COUNT(*) AS snapshot_count,
                       MAX(fetched_at) AS latest_fetched_at,
                       MAX(item_count) AS largest_snapshot
                FROM source_snapshots
                GROUP BY source
                ORDER BY source
                """
            ).fetchall()
        return [dict(row) for row in rows]
