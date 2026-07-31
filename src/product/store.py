from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.product.contracts import LIFECYCLE_LABELS


PRODUCT_DATABASE_NAME = "opportunity_radar_product.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def ensure_product_schema(database_path: str | Path) -> None:
    with _connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS product_workspaces (
                opportunity_key TEXT PRIMARY KEY,
                opportunity_url TEXT NOT NULL DEFAULT '',
                opportunity_title TEXT NOT NULL DEFAULT '',
                lifecycle_state TEXT NOT NULL DEFAULT 'detected',
                problem_statement TEXT NOT NULL DEFAULT '',
                user_segment TEXT NOT NULL DEFAULT '',
                buyer_hypothesis TEXT NOT NULL DEFAULT '',
                solution_format TEXT NOT NULL DEFAULT '',
                monetization_hypothesis TEXT NOT NULL DEFAULT '',
                acquisition_channel TEXT NOT NULL DEFAULT '',
                smallest_test TEXT NOT NULL DEFAULT '',
                price_test_hypothesis TEXT NOT NULL DEFAULT '',
                success_evidence TEXT NOT NULL DEFAULT '',
                discard_evidence TEXT NOT NULL DEFAULT '',
                budget_limit TEXT NOT NULL DEFAULT '',
                weekly_hours_limit TEXT NOT NULL DEFAULT '',
                target_validation_date TEXT NOT NULL DEFAULT '',
                next_action TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS product_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_key TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                raw_excerpt TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(opportunity_key)
                    REFERENCES product_workspaces(opportunity_key)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS product_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT '',
                amount_brl REAL,
                hours_spent REAL,
                cost_brl REAL,
                notes TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(opportunity_key)
                    REFERENCES product_workspaces(opportunity_key)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS product_translations (
                opportunity_key TEXT NOT NULL,
                field_name TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                source_language TEXT NOT NULL DEFAULT 'auto',
                target_language TEXT NOT NULL DEFAULT 'pt-BR',
                original_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'manual',
                model TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(opportunity_key, field_name)
            );

            CREATE INDEX IF NOT EXISTS idx_product_evidence_key
                ON product_evidence(opportunity_key);
            CREATE INDEX IF NOT EXISTS idx_product_events_key
                ON product_events(opportunity_key);
            CREATE INDEX IF NOT EXISTS idx_product_events_type
                ON product_events(event_type);
            """
        )


def _read_table(database_path: str | Path, table_name: str) -> pd.DataFrame:
    ensure_product_schema(database_path)
    with _connect(database_path) as connection:
        return pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection)


def load_workspaces(database_path: str | Path) -> pd.DataFrame:
    return _read_table(database_path, "product_workspaces")


def load_evidence(database_path: str | Path) -> pd.DataFrame:
    return _read_table(database_path, "product_evidence")


def load_events(database_path: str | Path) -> pd.DataFrame:
    return _read_table(database_path, "product_events")


def load_translations(database_path: str | Path) -> pd.DataFrame:
    return _read_table(database_path, "product_translations")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def upsert_workspace(
    database_path: str | Path,
    opportunity_key: str,
    values: Mapping[str, Any],
) -> None:
    ensure_product_schema(database_path)
    state = _clean(values.get("lifecycle_state")) or "detected"
    if state not in LIFECYCLE_LABELS:
        raise ValueError(f"Estado de ciclo de vida inválido: {state}")

    now = utc_now()
    fields = (
        "opportunity_url",
        "opportunity_title",
        "lifecycle_state",
        "problem_statement",
        "user_segment",
        "buyer_hypothesis",
        "solution_format",
        "monetization_hypothesis",
        "acquisition_channel",
        "smallest_test",
        "price_test_hypothesis",
        "success_evidence",
        "discard_evidence",
        "budget_limit",
        "weekly_hours_limit",
        "target_validation_date",
        "next_action",
        "notes",
    )
    payload = {field: _clean(values.get(field)) for field in fields}
    payload["lifecycle_state"] = state

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO product_workspaces (
                opportunity_key, opportunity_url, opportunity_title,
                lifecycle_state, problem_statement, user_segment,
                buyer_hypothesis, solution_format, monetization_hypothesis,
                acquisition_channel, smallest_test, price_test_hypothesis,
                success_evidence, discard_evidence, budget_limit,
                weekly_hours_limit, target_validation_date, next_action,
                notes, created_at, updated_at
            ) VALUES (
                :opportunity_key, :opportunity_url, :opportunity_title,
                :lifecycle_state, :problem_statement, :user_segment,
                :buyer_hypothesis, :solution_format, :monetization_hypothesis,
                :acquisition_channel, :smallest_test, :price_test_hypothesis,
                :success_evidence, :discard_evidence, :budget_limit,
                :weekly_hours_limit, :target_validation_date, :next_action,
                :notes, :created_at, :updated_at
            )
            ON CONFLICT(opportunity_key) DO UPDATE SET
                opportunity_url = excluded.opportunity_url,
                opportunity_title = excluded.opportunity_title,
                lifecycle_state = excluded.lifecycle_state,
                problem_statement = excluded.problem_statement,
                user_segment = excluded.user_segment,
                buyer_hypothesis = excluded.buyer_hypothesis,
                solution_format = excluded.solution_format,
                monetization_hypothesis = excluded.monetization_hypothesis,
                acquisition_channel = excluded.acquisition_channel,
                smallest_test = excluded.smallest_test,
                price_test_hypothesis = excluded.price_test_hypothesis,
                success_evidence = excluded.success_evidence,
                discard_evidence = excluded.discard_evidence,
                budget_limit = excluded.budget_limit,
                weekly_hours_limit = excluded.weekly_hours_limit,
                target_validation_date = excluded.target_validation_date,
                next_action = excluded.next_action,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            {
                "opportunity_key": opportunity_key,
                **payload,
                "created_at": now,
                "updated_at": now,
            },
        )


def ensure_workspace(
    database_path: str | Path,
    opportunity_key: str,
    *,
    opportunity_url: str = "",
    opportunity_title: str = "",
) -> None:
    ensure_product_schema(database_path)
    with _connect(database_path) as connection:
        existing = connection.execute(
            "SELECT 1 FROM product_workspaces WHERE opportunity_key = ?",
            (opportunity_key,),
        ).fetchone()
    if existing is None:
        upsert_workspace(
            database_path,
            opportunity_key,
            {
                "opportunity_url": opportunity_url,
                "opportunity_title": opportunity_title,
                "lifecycle_state": "detected",
            },
        )


def add_evidence(
    database_path: str | Path,
    opportunity_key: str,
    *,
    evidence_type: str,
    direction: str,
    summary: str,
    source_url: str = "",
    raw_excerpt: str = "",
    occurred_at: str = "",
) -> int:
    if not _clean(summary):
        raise ValueError("Resumo da evidência é obrigatório.")
    ensure_workspace(database_path, opportunity_key)
    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO product_evidence (
                opportunity_key, evidence_type, direction, summary,
                source_url, raw_excerpt, occurred_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity_key,
                _clean(evidence_type),
                _clean(direction),
                _clean(summary),
                _clean(source_url),
                _clean(raw_excerpt),
                _clean(occurred_at),
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def _optional_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Valor numérico inválido: {value!r}") from exc


def add_event(
    database_path: str | Path,
    opportunity_key: str,
    *,
    event_type: str,
    outcome: str = "",
    amount_brl: Any = None,
    hours_spent: Any = None,
    cost_brl: Any = None,
    notes: str = "",
    occurred_at: str = "",
) -> int:
    ensure_workspace(database_path, opportunity_key)
    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO product_events (
                opportunity_key, event_type, outcome, amount_brl,
                hours_spent, cost_brl, notes, occurred_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity_key,
                _clean(event_type),
                _clean(outcome),
                _optional_number(amount_brl),
                _optional_number(hours_spent),
                _optional_number(cost_brl),
                _clean(notes),
                _clean(occurred_at) or utc_now(),
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def upsert_translation(
    database_path: str | Path,
    opportunity_key: str,
    *,
    field_name: str,
    original_text: str,
    translated_text: str,
    source_language: str = "auto",
    target_language: str = "pt-BR",
    provider: str = "manual",
    model: str = "",
) -> None:
    ensure_product_schema(database_path)
    original = str(original_text)
    source_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO product_translations (
                opportunity_key, field_name, source_hash, source_language,
                target_language, original_text, translated_text, provider,
                model, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(opportunity_key, field_name) DO UPDATE SET
                source_hash = excluded.source_hash,
                source_language = excluded.source_language,
                target_language = excluded.target_language,
                original_text = excluded.original_text,
                translated_text = excluded.translated_text,
                provider = excluded.provider,
                model = excluded.model,
                updated_at = excluded.updated_at
            """,
            (
                opportunity_key,
                _clean(field_name),
                source_hash,
                _clean(source_language) or "auto",
                _clean(target_language) or "pt-BR",
                original,
                str(translated_text),
                _clean(provider) or "manual",
                _clean(model),
                utc_now(),
            ),
        )
