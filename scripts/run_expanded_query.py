from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.query_expansion import QueryExpansionRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Opportunity Radar with deterministic query expansion."
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--minimum-score", type=float, default=0)
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=15.0)
    parser.add_argument("--inter-query-delay-seconds", type=float, default=7.0)
    parser.add_argument(
        "--database",
        default=str(PROJECT_DIR / "data" / "opportunity_radar.db"),
    )
    return parser.parse_args()


def print_summary(database_path: Path, run_id: int) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                v.position,
                v.query,
                v.is_original,
                v.status,
                v.pipeline_status,
                v.attempt_count,
                v.collected_matches,
                v.new_opportunities,
                v.error_message,
                COUNT(m.id) AS stored_matches
            FROM query_expansion_variations AS v
            LEFT JOIN opportunity_query_matches AS m
                ON m.variation_id = v.id
            WHERE v.expansion_run_id = ?
            GROUP BY v.id
            ORDER BY v.position
            """,
            (run_id,),
        ).fetchall()

    print("\nVARIATIONS")
    for row in rows:
        kind = "original" if row["is_original"] else "variation"
        print(
            f"- [{kind}] {row['query']} | "
            f"status={row['status']} | "
            f"pipeline={row['pipeline_status']} | "
            f"attempts={row['attempt_count']} | "
            f"matches={row['stored_matches']} | "
            f"new={row['new_opportunities']}"
        )
        if row["error_message"]:
            print(f"  error={row['error_message']}")


def main() -> int:
    args = parse_args()
    database_path = Path(args.database).resolve()
    runner = QueryExpansionRunner(
        project_dir=PROJECT_DIR,
        database_path=database_path,
        max_attempts=args.max_attempts,
        retry_delay_seconds=args.retry_delay_seconds,
        inter_query_delay_seconds=args.inter_query_delay_seconds,
    )
    summary = runner.run(
        original_query=args.query,
        limit=args.limit,
        minimum_score=args.minimum_score,
        top=args.top,
    )

    print("\n" + "=" * 78)
    print("SPRINT 9.4 — QUERY EXPANSION SUMMARY")
    print("=" * 78)
    print(f"Run ID: {summary.run_id}")
    print(f"Original query: {summary.original_query}")
    print(f"Status: {summary.status}")
    print(f"Variations: {summary.successful_variations}/{summary.variation_count}")
    print(f"Unique opportunities: {summary.unique_opportunities}")
    print(f"Matches across variations: {summary.total_matches}")
    print(f"Duplicate matches consolidated: {summary.duplicate_matches}")
    print(f"SQLite: {database_path}")
    print_summary(database_path, summary.run_id)

    return 0 if summary.status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
