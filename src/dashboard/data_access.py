from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


CURATION_DATABASE_NAME = "opportunity_radar_curation.db"


@dataclass(frozen=True)
class RadarDataset:
    databases: pd.DataFrame
    opportunities: pd.DataFrame
    expansion_runs: pd.DataFrame
    variations: pd.DataFrame
    matches: pd.DataFrame
    collection_runs: pd.DataFrame
    inventory: pd.DataFrame


EMPTY_DATABASE_COLUMNS = [
    "database_file",
    "database_path",
    "size_bytes",
    "modified_at",
    "table_count",
]


def discover_databases(data_dir: str | Path) -> list[Path]:
    root = Path(data_dir).expanduser().resolve()
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.db")
        if path.is_file()
        and path.stat().st_size > 0
        and path.name != CURATION_DATABASE_NAME
    )


def _connect_read_only(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{database_path.as_posix()}?mode=ro",
        uri=True,
        timeout=10,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def list_tables(database_path: str | Path) -> list[str]:
    path = Path(database_path).resolve()
    with _connect_read_only(path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    return [str(row["name"]) for row in rows]


def read_table(database_path: str | Path, table_name: str) -> pd.DataFrame:
    path = Path(database_path).resolve()
    with _connect_read_only(path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        if exists is None:
            return pd.DataFrame()
        query = f"SELECT * FROM {_quote_identifier(table_name)}"
        return pd.read_sql_query(query, connection)


def _append_database_metadata(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    result["database_file"] = path.name
    result["database_path"] = str(path)
    return result


def _first_column(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    by_lower = {str(column).casefold(): str(column) for column in frame.columns}
    for candidate in candidates:
        match = by_lower.get(candidate.casefold())
        if match:
            return match
    return None


def _series_or_default(
    frame: pd.DataFrame,
    candidates: Iterable[str],
    default: object = "",
) -> pd.Series:
    column = _first_column(frame, candidates)
    if column is None:
        return pd.Series([default] * len(frame), index=frame.index)
    return frame[column]


def _string_series(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").astype(str).str.strip()


def _numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def normalize_opportunities(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "database_file",
        "database_path",
        "opportunity_id",
        "source",
        "title",
        "url",
        "score",
        "level",
        "pain_categories",
        "created_at",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(index=frame.index)
    result["database_file"] = _string_series(
        _series_or_default(frame, ["database_file"])
    )
    result["database_path"] = _string_series(
        _series_or_default(frame, ["database_path"])
    )
    result["opportunity_id"] = _string_series(
        _series_or_default(frame, ["id", "opportunity_id"])
    )
    result["source"] = _string_series(
        _series_or_default(frame, ["source", "source_name", "platform"])
    )
    result["title"] = _string_series(
        _series_or_default(frame, ["title", "name"])
    )
    result["url"] = _string_series(
        _series_or_default(frame, ["url", "source_url", "external_url", "link"])
    )
    result["score"] = _numeric_series(
        _series_or_default(
            frame,
            [
                "score",
                "total_score",
                "final_score",
                "opportunity_score",
                "ranking_score",
                "weighted_score",
            ],
            default=None,
        )
    )
    result["level"] = _string_series(
        _series_or_default(
            frame,
            ["level", "score_level", "opportunity_level", "ranking_level"],
        )
    )
    result["pain_categories"] = _string_series(
        _series_or_default(
            frame,
            ["pain_categories", "pain_category", "pain_signals", "pains"],
        )
    )
    result["created_at"] = _string_series(
        _series_or_default(
            frame,
            [
                "created_at",
                "collected_at",
                "first_seen_at",
                "inserted_at",
                "timestamp",
                "published_at",
            ],
        )
    )
    result = result[result["url"].ne("") | result["title"].ne("")]
    return result.reset_index(drop=True)


def normalize_matches(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "database_file",
        "database_path",
        "expansion_run_id",
        "variation_id",
        "opportunity_id",
        "opportunity_url",
        "source",
        "title",
        "original_query",
        "matched_query",
        "first_seen_at",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(index=frame.index)
    for column in columns:
        result[column] = _string_series(_series_or_default(frame, [column]))
    return result.reset_index(drop=True)


def _unique_join(values: pd.Series) -> str:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value or "").strip()
        identity = value.casefold()
        if value and identity not in seen:
            seen.add(identity)
            ordered.append(value)
    return " | ".join(ordered)


def enrich_opportunities(
    opportunities: pd.DataFrame,
    matches: pd.DataFrame,
) -> pd.DataFrame:
    base = opportunities.copy()
    if base.empty and not matches.empty:
        base = pd.DataFrame(
            {
                "database_file": matches["database_file"],
                "database_path": matches["database_path"],
                "opportunity_id": matches["opportunity_id"],
                "source": matches["source"],
                "title": matches["title"],
                "url": matches["opportunity_url"],
                "score": pd.NA,
                "level": "",
                "pain_categories": "",
                "created_at": matches["first_seen_at"],
            }
        ).drop_duplicates(["database_path", "url"])

    for column, default in (
        ("original_queries", ""),
        ("matched_queries", ""),
        ("match_count", 0),
        ("variation_count", 0),
    ):
        if column not in base:
            base[column] = default

    if matches.empty:
        return base.reset_index(drop=True)

    rollup = (
        matches.groupby(
            ["database_path", "opportunity_url"],
            dropna=False,
            as_index=False,
        )
        .agg(
            original_queries=("original_query", _unique_join),
            matched_queries=("matched_query", _unique_join),
            match_count=("matched_query", "size"),
            variation_count=("matched_query", "nunique"),
            match_source=("source", _unique_join),
            match_title=("title", _unique_join),
        )
    )

    result = base.merge(
        rollup,
        how="outer",
        left_on=["database_path", "url"],
        right_on=["database_path", "opportunity_url"],
        suffixes=("", "_rollup"),
    )
    result["url"] = _string_series(result["url"]).mask(
        _string_series(result["url"]).eq(""),
        _string_series(result["opportunity_url"]),
    )
    result["source"] = _string_series(result["source"]).mask(
        _string_series(result["source"]).eq(""),
        _string_series(result["match_source"]),
    )
    result["title"] = _string_series(result["title"]).mask(
        _string_series(result["title"]).eq(""),
        _string_series(result["match_title"]),
    )
    result["database_file"] = _string_series(result["database_file"])
    result["original_queries"] = _string_series(result["original_queries_rollup"])
    result["matched_queries"] = _string_series(result["matched_queries_rollup"])
    result["match_count"] = pd.to_numeric(
        result["match_count_rollup"], errors="coerce"
    ).fillna(0).astype(int)
    result["variation_count"] = pd.to_numeric(
        result["variation_count_rollup"], errors="coerce"
    ).fillna(0).astype(int)
    removable = [
        "opportunity_url",
        "match_source",
        "match_title",
        "original_queries_rollup",
        "matched_queries_rollup",
        "match_count_rollup",
        "variation_count_rollup",
    ]
    result = result.drop(columns=[c for c in removable if c in result.columns])
    return result.reset_index(drop=True)


def load_radar_data(
    data_dir: str | Path,
    selected_database_files: Iterable[str] | None = None,
) -> RadarDataset:
    selected = {
        str(value) for value in selected_database_files or [] if str(value).strip()
    }
    database_paths = discover_databases(data_dir)
    if selected:
        database_paths = [path for path in database_paths if path.name in selected]

    database_records: list[dict[str, object]] = []
    inventory_records: list[dict[str, object]] = []
    table_frames: dict[str, list[pd.DataFrame]] = {
        "opportunities": [],
        "query_expansion_runs": [],
        "query_expansion_variations": [],
        "opportunity_query_matches": [],
        "collection_runs": [],
    }

    for path in database_paths:
        try:
            tables = list_tables(path)
        except sqlite3.DatabaseError as exc:
            database_records.append(
                {
                    "database_file": path.name,
                    "database_path": str(path),
                    "size_bytes": path.stat().st_size,
                    "modified_at": path.stat().st_mtime,
                    "table_count": 0,
                    "status": f"ERROR: {exc}",
                }
            )
            continue

        database_records.append(
            {
                "database_file": path.name,
                "database_path": str(path),
                "size_bytes": path.stat().st_size,
                "modified_at": path.stat().st_mtime,
                "table_count": len(tables),
                "status": "OK",
            }
        )
        for table in tables:
            frame = read_table(path, table)
            inventory_records.append(
                {
                    "database_file": path.name,
                    "database_path": str(path),
                    "table_name": table,
                    "row_count": len(frame),
                    "column_count": len(frame.columns),
                    "columns": ", ".join(str(column) for column in frame.columns),
                }
            )
            if table in table_frames and not frame.empty:
                table_frames[table].append(_append_database_metadata(frame, path))

    def combine(name: str) -> pd.DataFrame:
        frames = [frame for frame in table_frames[name] if not frame.empty]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True, sort=False)

    raw_opportunities = combine("opportunities")
    raw_matches = combine("opportunity_query_matches")
    normalized_matches = normalize_matches(raw_matches)
    normalized_opportunities = enrich_opportunities(
        normalize_opportunities(raw_opportunities),
        normalized_matches,
    )

    databases = pd.DataFrame(database_records)
    if databases.empty:
        databases = pd.DataFrame(columns=EMPTY_DATABASE_COLUMNS + ["status"])

    return RadarDataset(
        databases=databases,
        opportunities=normalized_opportunities,
        expansion_runs=combine("query_expansion_runs"),
        variations=combine("query_expansion_variations"),
        matches=normalized_matches,
        collection_runs=combine("collection_runs"),
        inventory=pd.DataFrame(inventory_records),
    )
