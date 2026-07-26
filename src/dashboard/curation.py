from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


CURATION_STATUSES = ("valid", "review", "false_positive")
CURATION_LABELS = {
    "unreviewed": "⚪ Não revisada",
    "valid": "🟢 Válida",
    "review": "🟡 Revisar",
    "false_positive": "🔴 Falso positivo",
}
LABEL_TO_STATUS = {label: status for status, label in CURATION_LABELS.items()}


def ensure_curation_schema(database_path: str | Path) -> Path:
    path = Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_curation (
                opportunity_url TEXT PRIMARY KEY,
                status TEXT NOT NULL
                    CHECK (status IN ('valid', 'review', 'false_positive')),
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
    return path


def load_curation(database_path: str | Path) -> pd.DataFrame:
    path = ensure_curation_schema(database_path)
    with sqlite3.connect(path) as connection:
        frame = pd.read_sql_query(
            """
            SELECT opportunity_url, status, notes, updated_at
            FROM opportunity_curation
            ORDER BY updated_at DESC, opportunity_url
            """,
            connection,
        )
    if frame.empty:
        return pd.DataFrame(
            columns=["opportunity_url", "status", "notes", "updated_at"]
        )
    for column in ("opportunity_url", "status", "notes", "updated_at"):
        frame[column] = frame[column].astype("string").fillna("").astype(str).str.strip()
    return frame


def save_curation(
    database_path: str | Path,
    opportunity_url: str,
    status: str,
    notes: str = "",
) -> None:
    url = str(opportunity_url or "").strip()
    normalized_status = str(status or "").strip().casefold()
    normalized_notes = str(notes or "").strip()

    if not url:
        raise ValueError("A oportunidade precisa possuir URL para ser classificada.")

    path = ensure_curation_schema(database_path)

    if normalized_status == "unreviewed":
        with sqlite3.connect(path) as connection:
            connection.execute(
                "DELETE FROM opportunity_curation WHERE opportunity_url = ?",
                (url,),
            )
            connection.commit()
        return

    if normalized_status not in CURATION_STATUSES:
        raise ValueError(f"Status de curadoria inválido: {status}")

    updated_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO opportunity_curation (
                opportunity_url,
                status,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(opportunity_url) DO UPDATE SET
                status = excluded.status,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (url, normalized_status, normalized_notes, updated_at),
        )
        connection.commit()


def attach_curation(
    opportunities: pd.DataFrame,
    curation: pd.DataFrame,
) -> pd.DataFrame:
    result = opportunities.copy()
    if result.empty:
        for column, default in (
            ("curation_status", "unreviewed"),
            ("curation_label", CURATION_LABELS["unreviewed"]),
            ("curation_notes", ""),
            ("curation_updated_at", ""),
        ):
            result[column] = default
        return result

    if curation.empty:
        result["curation_status"] = "unreviewed"
        result["curation_notes"] = ""
        result["curation_updated_at"] = ""
    else:
        prepared = curation.rename(
            columns={
                "opportunity_url": "url",
                "status": "curation_status",
                "notes": "curation_notes",
                "updated_at": "curation_updated_at",
            }
        )
        result = result.merge(prepared, on="url", how="left")
        result["curation_status"] = (
            result["curation_status"]
            .astype("string")
            .fillna("unreviewed")
            .astype(str)
            .str.strip()
            .replace("", "unreviewed")
        )
        result["curation_notes"] = (
            result["curation_notes"].astype("string").fillna("").astype(str).str.strip()
        )
        result["curation_updated_at"] = (
            result["curation_updated_at"]
            .astype("string")
            .fillna("")
            .astype(str)
            .str.strip()
        )

    result["curation_label"] = result["curation_status"].map(CURATION_LABELS).fillna(
        CURATION_LABELS["unreviewed"]
    )
    return result
