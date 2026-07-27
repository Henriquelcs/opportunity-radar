from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


CONNECTED_SOURCES: tuple[tuple[str, str], ...] = (
    ("github", "GitHub"),
    ("stackoverflow", "Stack Overflow"),
    ("softwarerecs", "Software Recommendations"),
    ("webapps", "Web Applications"),
    ("hackernews", "Hacker News"),
    ("devto", "DEV Community"),
)

SOURCE_LABELS = dict(CONNECTED_SOURCES)
COMPLETED_STATUSES = {"SUCCESS", "PARTIAL_SUCCESS"}
USABLE_SOURCE_STATUSES = {"LIVE", "CACHE"}


@dataclass(frozen=True)
class LandingSummary:
    operation_status: str
    cycle_id: str
    opportunities: int
    opportunity_sources: int
    connected_sources: int
    live_sources: int
    cached_sources: int
    unavailable_sources: int
    queries_completed: int
    queries_total: int
    variations_completed: int
    variations_total: int
    duplicates_removed: int
    pending_review: int
    latest_at: str


def _string_series(
    frame: pd.DataFrame,
    column: str,
    default: str = "",
) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .astype(str)
        .str.strip()
    )


def _numeric_series(
    frame: pd.DataFrame,
    column: str,
) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([pd.NA] * len(frame), index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _preferred_operational_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "database_file" not in frame.columns:
        return frame.copy()

    database_files = _string_series(frame, "database_file")
    preferred = frame[
        database_files.eq("opportunity_radar_operational.db")
    ].copy()
    return preferred if not preferred.empty else frame.copy()


def _datetime_series(
    frame: pd.DataFrame,
    candidates: Iterable[str],
) -> pd.Series:
    result = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
    for column in candidates:
        if column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce", utc=True)
        result = result.fillna(parsed)
    return result


def latest_source_cycle(source_sync_runs: pd.DataFrame) -> pd.DataFrame:
    frame = _preferred_operational_rows(source_sync_runs)
    if frame.empty:
        return frame

    frame = frame.copy()
    frame["_cycle"] = _string_series(frame, "cycle_id")
    frame["_time"] = _datetime_series(
        frame,
        ("created_at", "snapshot_at"),
    )

    valid_cycles = frame[frame["_cycle"].ne("")]
    if not valid_cycles.empty:
        cycle_order = (
            valid_cycles.groupby("_cycle", dropna=False)["_time"]
            .max()
            .sort_values()
        )
        latest_cycle_id = str(cycle_order.index[-1])
        return frame[frame["_cycle"].eq(latest_cycle_id)].drop(
            columns=["_cycle", "_time"],
            errors="ignore",
        )

    if frame["_time"].notna().any():
        latest_time = frame["_time"].max()
        return frame[frame["_time"].eq(latest_time)].drop(
            columns=["_cycle", "_time"],
            errors="ignore",
        )

    return frame.tail(len(CONNECTED_SOURCES)).drop(
        columns=["_cycle", "_time"],
        errors="ignore",
    )


def latest_expansion_runs(
    expansion_runs: pd.DataFrame,
    source_cycle: pd.DataFrame,
    expected_queries: int = 3,
) -> pd.DataFrame:
    frame = _preferred_operational_rows(expansion_runs)
    if frame.empty:
        return frame

    frame = frame.copy()
    frame["_id"] = _numeric_series(frame, "id")
    frame["_started"] = _datetime_series(
        frame,
        ("started_at", "created_at"),
    )

    cycle_start = pd.NaT
    if not source_cycle.empty:
        source_times = _datetime_series(
            source_cycle,
            ("created_at", "snapshot_at"),
        )
        if source_times.notna().any():
            cycle_start = source_times.min()

    if pd.notna(cycle_start) and frame["_started"].notna().any():
        recent = frame[
            frame["_started"].ge(cycle_start - pd.Timedelta(minutes=2))
        ].copy()
        if not recent.empty:
            frame = recent

    sort_columns = [
        column
        for column in ("_started", "_id")
        if column in frame.columns
    ]
    if sort_columns:
        frame = frame.sort_values(sort_columns, na_position="first")

    if len(frame) > expected_queries:
        frame = frame.tail(expected_queries)

    return frame.drop(
        columns=["_id", "_started"],
        errors="ignore",
    )


def latest_variations(
    variations: pd.DataFrame,
    expansion_runs: pd.DataFrame,
) -> pd.DataFrame:
    if variations.empty or expansion_runs.empty:
        return variations.iloc[0:0].copy()

    frame = _preferred_operational_rows(variations)
    if "expansion_run_id" not in frame.columns or "id" not in expansion_runs.columns:
        return frame.iloc[0:0].copy()

    numeric_run_ids = set(
        pd.to_numeric(
            expansion_runs["id"],
            errors="coerce",
        ).dropna().astype(int).tolist()
    )
    numeric_variation_ids = pd.to_numeric(
        frame["expansion_run_id"],
        errors="coerce",
    )
    if numeric_run_ids:
        numeric_matches = numeric_variation_ids.isin(numeric_run_ids)
        if numeric_matches.any():
            return frame[numeric_matches].copy()

    run_ids = {
        str(value).strip()
        for value in expansion_runs["id"].tolist()
        if str(value).strip()
    }
    if not run_ids:
        return frame.iloc[0:0].copy()

    ids = _string_series(frame, "expansion_run_id")
    return frame[ids.isin(run_ids)].copy()


def _completed_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    statuses = _string_series(frame, "status").str.upper()
    return int(statuses.isin(COMPLETED_STATUSES).sum())


def _format_latest_at(
    source_cycle: pd.DataFrame,
    expansion_runs: pd.DataFrame,
) -> str:
    candidates: list[pd.Timestamp] = []
    for frame, columns in (
        (source_cycle, ("snapshot_at", "created_at")),
        (expansion_runs, ("finished_at", "started_at")),
    ):
        if frame.empty:
            continue
        parsed = _datetime_series(frame, columns)
        if parsed.notna().any():
            candidates.append(parsed.max())

    if not candidates:
        return "Sem horário registrado"

    latest = max(candidates)
    return latest.strftime("%d/%m/%Y %H:%M UTC")


def build_landing_summary(
    opportunities: pd.DataFrame,
    expansion_runs: pd.DataFrame,
    variations: pd.DataFrame,
    source_sync_runs: pd.DataFrame,
) -> LandingSummary:
    source_cycle = latest_source_cycle(source_sync_runs)
    latest_runs = latest_expansion_runs(expansion_runs, source_cycle)
    latest_variation_rows = latest_variations(variations, latest_runs)

    source_statuses = _string_series(source_cycle, "status").str.upper()
    live_sources = int(source_statuses.eq("LIVE").sum())
    cached_sources = int(source_statuses.eq("CACHE").sum())
    unavailable_sources = int(
        (~source_statuses.isin(USABLE_SOURCE_STATUSES)).sum()
    )

    queries_total = int(len(latest_runs))
    queries_completed = _completed_count(latest_runs)
    variations_total = int(len(latest_variation_rows))
    variations_completed = _completed_count(latest_variation_rows)

    if not source_cycle.empty:
        cycle_id_values = _string_series(source_cycle, "cycle_id")
        cycle_id = next(
            (value for value in cycle_id_values if value),
            "",
        )
    else:
        cycle_id = ""

    run_statuses = _string_series(latest_runs, "status").str.upper()
    if (
        len(source_statuses) > 0
        and source_statuses.eq("LIVE").all()
        and len(run_statuses) > 0
        and run_statuses.eq("SUCCESS").all()
    ):
        operation_status = "SUCCESS"
    elif (
        source_statuses.isin(USABLE_SOURCE_STATUSES).any()
        and queries_completed > 0
    ):
        operation_status = "DEGRADED"
    elif queries_completed > 0:
        operation_status = "DEGRADED"
    elif queries_total > 0:
        operation_status = "FAILED"
    else:
        operation_status = "UNKNOWN"

    duplicate_values = _numeric_series(latest_runs, "duplicate_matches")
    duplicates_removed = int(duplicate_values.fillna(0).sum())

    if opportunities.empty:
        opportunity_sources = 0
        pending_review = 0
    else:
        opportunity_sources = int(
            _string_series(opportunities, "source")
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )
        curation_status = _string_series(
            opportunities,
            "curation_status",
            default="unreviewed",
        ).str.casefold()
        pending_review = int(curation_status.eq("unreviewed").sum())

    return LandingSummary(
        operation_status=operation_status,
        cycle_id=cycle_id,
        opportunities=int(len(opportunities)),
        opportunity_sources=opportunity_sources,
        connected_sources=len(CONNECTED_SOURCES),
        live_sources=live_sources,
        cached_sources=cached_sources,
        unavailable_sources=unavailable_sources,
        queries_completed=queries_completed,
        queries_total=queries_total,
        variations_completed=variations_completed,
        variations_total=variations_total,
        duplicates_removed=duplicates_removed,
        pending_review=pending_review,
        latest_at=_format_latest_at(source_cycle, latest_runs),
    )


def rank_opportunities(
    opportunities: pd.DataFrame,
    limit: int = 6,
) -> pd.DataFrame:
    if opportunities.empty:
        return opportunities.copy()

    result = opportunities.copy()
    result["_status"] = _string_series(
        result,
        "curation_status",
        default="unreviewed",
    ).str.casefold()
    result = result[result["_status"].ne("false_positive")].copy()

    result["_score"] = _numeric_series(result, "score").fillna(-1)
    result["_matches"] = _numeric_series(result, "match_count").fillna(0)
    result["_review_priority"] = result["_status"].map(
        {
            "valid": 0,
            "review": 1,
            "unreviewed": 2,
        }
    ).fillna(3)

    result["_title_key"] = (
        _string_series(result, "title")
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
    )
    result["_url_key"] = _string_series(result, "url")
    result["_dedupe_key"] = result["_title_key"].mask(
        result["_title_key"].eq(""),
        result["_url_key"],
    )

    result = result.sort_values(
        ["_score", "_matches", "_review_priority"],
        ascending=[False, False, True],
        na_position="last",
    )
    result = result.drop_duplicates("_dedupe_key", keep="first")

    return result.head(max(0, int(limit))).drop(
        columns=[
            "_status",
            "_score",
            "_matches",
            "_review_priority",
            "_title_key",
            "_url_key",
            "_dedupe_key",
        ],
        errors="ignore",
    )


def source_status_overview(
    source_sync_runs: pd.DataFrame,
) -> pd.DataFrame:
    cycle = latest_source_cycle(source_sync_runs)
    by_source: dict[str, dict[str, object]] = {}

    if not cycle.empty:
        for _, row in cycle.iterrows():
            source = str(row.get("source", "") or "").strip().casefold()
            if not source:
                continue
            by_source[source] = {
                "status": str(row.get("status", "") or "").strip().upper(),
                "item_count": int(
                    pd.to_numeric(
                        pd.Series([row.get("item_count")]),
                        errors="coerce",
                    ).fillna(0).iloc[0]
                ),
                "new_item_count": int(
                    pd.to_numeric(
                        pd.Series([row.get("new_item_count")]),
                        errors="coerce",
                    ).fillna(0).iloc[0]
                ),
            }

    labels = {
        "LIVE": "Atualizada",
        "CACHE": "Cache reutilizado",
        "SKIPPED": "Indisponível",
        "ERROR": "Erro",
        "": "Sem registro",
    }

    records: list[dict[str, object]] = []
    for source, label in CONNECTED_SOURCES:
        state = by_source.get(
            source,
            {
                "status": "",
                "item_count": 0,
                "new_item_count": 0,
            },
        )
        status = str(state["status"])
        records.append(
            {
                "Fonte": label,
                "Estado": labels.get(status, status.title() or "Sem registro"),
                "Itens disponíveis": int(state["item_count"]),
                "Novos no ciclo": int(state["new_item_count"]),
            }
        )

    return pd.DataFrame(records)
