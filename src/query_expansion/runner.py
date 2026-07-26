from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from src.query_expansion.query_expander import QueryExpander, QueryVariation


Executor = Callable[..., subprocess.CompletedProcess[str]]
Sleeper = Callable[[float], None]


@dataclass(frozen=True, slots=True)
class OpportunityReference:
    url: str
    opportunity_id: int | str | None = None
    source: str = ""
    title: str = ""


@dataclass(frozen=True, slots=True)
class ExpansionSummary:
    run_id: int
    original_query: str
    status: str
    variation_count: int
    successful_variations: int
    failed_variations: int
    total_matches: int
    unique_opportunities: int
    duplicate_matches: int


@dataclass(frozen=True, slots=True)
class VariationExecution:
    started_at: str
    result: subprocess.CompletedProcess[str]
    pipeline_status: str
    references: tuple[OpportunityReference, ...]
    new_opportunities: int
    error_message: str | None
    attempt_count: int


class QueryExpansionRunner:
    """Run the existing Opportunity Radar CLI once for every query variation."""

    RETRYABLE_PIPELINE_STATUSES = frozenset({"PARTIAL_SUCCESS", "FAILED"})

    def __init__(
        self,
        project_dir: str | Path,
        database_path: str | Path,
        expander: QueryExpander | None = None,
        executor: Executor | None = None,
        sleeper: Sleeper | None = None,
        verbose: bool = True,
        max_attempts: int = 3,
        retry_delay_seconds: float = 15.0,
        inter_query_delay_seconds: float = 7.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if retry_delay_seconds < 0 or inter_query_delay_seconds < 0:
            raise ValueError("delay values cannot be negative")

        self.project_dir = Path(project_dir).resolve()
        self.database_path = Path(database_path).resolve()
        self.expander = expander or QueryExpander()
        self.executor = executor or subprocess.run
        self.sleeper = sleeper or time.sleep
        self.verbose = verbose
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.inter_query_delay_seconds = inter_query_delay_seconds

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _table_columns(
        connection: sqlite3.Connection,
        table_name: str,
    ) -> set[str]:
        return {
            str(row["name"])
            for row in connection.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
        }

    def _ensure_metadata_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS query_expansion_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_query TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    variation_count INTEGER NOT NULL DEFAULT 0,
                    successful_variations INTEGER NOT NULL DEFAULT 0,
                    failed_variations INTEGER NOT NULL DEFAULT 0,
                    total_matches INTEGER NOT NULL DEFAULT 0,
                    unique_opportunities INTEGER NOT NULL DEFAULT 0,
                    duplicate_matches INTEGER NOT NULL DEFAULT 0,
                    database_path TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS query_expansion_variations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expansion_run_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    is_original INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    return_code INTEGER,
                    pipeline_status TEXT,
                    collected_matches INTEGER NOT NULL DEFAULT 0,
                    new_opportunities INTEGER NOT NULL DEFAULT 0,
                    attempt_count INTEGER NOT NULL DEFAULT 1,
                    error_message TEXT,
                    FOREIGN KEY (expansion_run_id)
                        REFERENCES query_expansion_runs(id)
                        ON DELETE CASCADE,
                    UNIQUE (expansion_run_id, position),
                    UNIQUE (expansion_run_id, query)
                );

                CREATE TABLE IF NOT EXISTS opportunity_query_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expansion_run_id INTEGER NOT NULL,
                    variation_id INTEGER NOT NULL,
                    opportunity_id TEXT,
                    opportunity_url TEXT NOT NULL,
                    source TEXT,
                    title TEXT,
                    original_query TEXT NOT NULL,
                    matched_query TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    FOREIGN KEY (expansion_run_id)
                        REFERENCES query_expansion_runs(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (variation_id)
                        REFERENCES query_expansion_variations(id)
                        ON DELETE CASCADE,
                    UNIQUE (expansion_run_id, variation_id, opportunity_url)
                );

                CREATE INDEX IF NOT EXISTS idx_query_expansion_runs_query
                    ON query_expansion_runs(original_query);

                CREATE INDEX IF NOT EXISTS idx_query_variations_run
                    ON query_expansion_variations(expansion_run_id);

                CREATE INDEX IF NOT EXISTS idx_query_matches_url
                    ON opportunity_query_matches(opportunity_url);

                CREATE INDEX IF NOT EXISTS idx_query_matches_matched_query
                    ON opportunity_query_matches(matched_query);
                """
            )

            columns = self._table_columns(
                connection,
                "query_expansion_variations",
            )
            if "attempt_count" not in columns:
                connection.execute(
                    """
                    ALTER TABLE query_expansion_variations
                    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1
                    """
                )

    def _table_exists(self, connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _snapshot_opportunities(self) -> dict[str, OpportunityReference]:
        if not self.database_path.exists():
            return {}

        with self._connect() as connection:
            if not self._table_exists(connection, "opportunities"):
                return {}

            columns = [
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(opportunities)"
                ).fetchall()
            ]
            by_lower = {column.casefold(): column for column in columns}

            def choose(*candidates: str) -> str | None:
                for candidate in candidates:
                    if candidate.casefold() in by_lower:
                        return by_lower[candidate.casefold()]
                return None

            url_column = choose("url", "source_url", "external_url", "link")
            if url_column is None:
                return {}

            id_column = choose("id", "opportunity_id")
            source_column = choose("source", "source_name", "platform")
            title_column = choose("title", "name")

            selected_columns = [url_column]
            for optional_column in (id_column, source_column, title_column):
                if optional_column and optional_column not in selected_columns:
                    selected_columns.append(optional_column)

            sql = "SELECT " + ", ".join(
                self._quote_identifier(column) for column in selected_columns
            ) + " FROM opportunities"

            snapshot: dict[str, OpportunityReference] = {}
            for row in connection.execute(sql).fetchall():
                url = str(row[url_column] or "").strip()
                if not url:
                    continue
                snapshot[url] = OpportunityReference(
                    url=url,
                    opportunity_id=row[id_column] if id_column else None,
                    source=str(row[source_column] or "") if source_column else "",
                    title=str(row[title_column] or "") if title_column else "",
                )
            return snapshot

    @staticmethod
    def _parse_opportunities(output: str) -> dict[str, OpportunityReference]:
        parsed: dict[str, OpportunityReference] = {}
        source = ""
        title = ""

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line.startswith("Fonte:"):
                source = line.split(":", 1)[1].strip()
            elif line.startswith("Título:"):
                title = line.split(":", 1)[1].strip()
            elif line.startswith("URL:"):
                url = line.split(":", 1)[1].strip()
                if url:
                    parsed[url] = OpportunityReference(
                        url=url,
                        source=source,
                        title=title,
                    )
                source = ""
                title = ""

        return parsed

    @staticmethod
    def _extract_pipeline_status(output: str, return_code: int) -> str:
        matches = re.findall(
            r"(?m)^Status:\s*([A-Z_]+)\s*$",
            output,
        )
        if matches:
            return matches[-1]
        return "SUCCESS" if return_code == 0 else "FAILED"

    @staticmethod
    def _diagnostic_excerpt(output: str) -> str:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        keywords = (
            "fontes com erro",
            "rate limit",
            "secondary rate",
            "403",
            "429",
            "timeout",
            "exception",
            "failure",
            "failed",
            "falha",
            "error",
            "erro",
        )
        selected = [
            line
            for line in lines
            if any(keyword in line.casefold() for keyword in keywords)
        ]
        if not selected:
            selected = lines[-8:]
        return "\n".join(selected[-12:])[-2000:]

    @classmethod
    def _failure_message(
        cls,
        result: subprocess.CompletedProcess[str],
    ) -> str:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = "\n".join(part for part in (stdout, stderr) if part)
        if combined:
            return cls._diagnostic_excerpt(combined)
        return f"return code {result.returncode}"

    def _create_expansion_run(
        self,
        original_query: str,
        variations: Iterable[QueryVariation],
        started_at: str,
    ) -> int:
        variations_list = list(variations)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_expansion_runs (
                    original_query,
                    status,
                    started_at,
                    variation_count,
                    database_path
                ) VALUES (?, 'RUNNING', ?, ?, ?)
                """,
                (
                    original_query,
                    started_at,
                    len(variations_list),
                    str(self.database_path),
                ),
            )
            return int(cursor.lastrowid)

    def _create_variation(
        self,
        run_id: int,
        variation: QueryVariation,
        started_at: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_expansion_variations (
                    expansion_run_id,
                    position,
                    query,
                    is_original,
                    status,
                    started_at
                ) VALUES (?, ?, ?, ?, 'RUNNING', ?)
                """,
                (
                    run_id,
                    variation.position,
                    variation.query,
                    int(variation.is_original),
                    started_at,
                ),
            )
            return int(cursor.lastrowid)

    def _opportunities_table_exists(self) -> bool:
        if not self.database_path.exists():
            return False
        with self._connect() as connection:
            return self._table_exists(connection, "opportunities")

    def _execute_collection(
        self,
        variation: QueryVariation,
        total_variations: int,
        limit: int,
        minimum_score: float,
        top: int,
    ) -> VariationExecution:
        started_at = self._utc_now()
        initial_snapshot = self._snapshot_opportunities()
        accumulated_parsed: dict[str, OpportunityReference] = {}
        final_result: subprocess.CompletedProcess[str] | None = None
        final_pipeline_status = "FAILED"
        final_error: str | None = None
        final_snapshot = initial_snapshot
        attempts_used = 0

        marker = "original" if variation.is_original else "variation"
        if self.verbose:
            print(f"\n{'=' * 78}")
            print(
                f"QUERY {variation.position + 1}/{total_variations} "
                f"[{marker}] {variation.query}"
            )
            print("=" * 78)

        command = [
            sys.executable,
            "main.py",
            "--query",
            variation.query,
            "--limit",
            str(limit),
            "--minimum-score",
            str(minimum_score),
            "--top",
            str(top),
            "--database",
            str(self.database_path),
        ]

        for attempt in range(1, self.max_attempts + 1):
            attempts_used = attempt
            result = self.executor(
                command,
                cwd=self.project_dir,
                text=True,
                capture_output=True,
            )
            final_result = result
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            combined_output = "\n".join(
                part for part in (stdout, stderr) if part
            )

            accumulated_parsed.update(
                self._parse_opportunities(combined_output)
            )
            final_snapshot = self._snapshot_opportunities()
            final_pipeline_status = self._extract_pipeline_status(
                combined_output,
                result.returncode,
            )

            is_success = (
                result.returncode == 0
                and final_pipeline_status == "SUCCESS"
            )

            if self.verbose:
                print(
                    f"Tentativa {attempt}/{self.max_attempts}: "
                    f"pipeline={final_pipeline_status} "
                    f"return_code={result.returncode}"
                )

            if is_success:
                final_error = None
                break

            final_error = self._failure_message(result)
            if self.verbose and final_error:
                print("Diagnóstico:")
                print(final_error)

            retryable = (
                final_pipeline_status in self.RETRYABLE_PIPELINE_STATUSES
                or result.returncode != 0
            )
            if not retryable or attempt >= self.max_attempts:
                break

            delay = self.retry_delay_seconds * attempt
            if self.verbose:
                print(f"Nova tentativa após backoff de {delay:.0f}s.")
            self.sleeper(delay)

        if final_result is None:
            raise RuntimeError("The query variation was not executed")

        new_urls = set(final_snapshot) - set(initial_snapshot)
        candidate_urls = set(accumulated_parsed) | new_urls
        references: list[OpportunityReference] = []

        for url in sorted(candidate_urls):
            database_reference = final_snapshot.get(url)
            parsed_reference = accumulated_parsed.get(url)
            if database_reference is None:
                continue
            references.append(
                OpportunityReference(
                    url=url,
                    opportunity_id=database_reference.opportunity_id,
                    source=database_reference.source
                    or (parsed_reference.source if parsed_reference else ""),
                    title=database_reference.title
                    or (parsed_reference.title if parsed_reference else ""),
                )
            )

        is_success = (
            final_result.returncode == 0
            and final_pipeline_status == "SUCCESS"
        )

        return VariationExecution(
            started_at=started_at,
            result=final_result,
            pipeline_status=final_pipeline_status,
            references=tuple(references),
            new_opportunities=len(new_urls),
            error_message=None if is_success else final_error,
            attempt_count=attempts_used,
        )

    def _record_matches(
        self,
        run_id: int,
        variation_id: int,
        original_query: str,
        matched_query: str,
        opportunities: Iterable[OpportunityReference],
    ) -> int:
        inserted = 0
        with self._connect() as connection:
            for opportunity in opportunities:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO opportunity_query_matches (
                        expansion_run_id,
                        variation_id,
                        opportunity_id,
                        opportunity_url,
                        source,
                        title,
                        original_query,
                        matched_query,
                        first_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        variation_id,
                        None
                        if opportunity.opportunity_id is None
                        else str(opportunity.opportunity_id),
                        opportunity.url,
                        opportunity.source,
                        opportunity.title,
                        original_query,
                        matched_query,
                        self._utc_now(),
                    ),
                )
                inserted += int(cursor.rowcount > 0)
        return inserted

    def _finish_variation(
        self,
        variation_id: int,
        status: str,
        return_code: int,
        pipeline_status: str,
        collected_matches: int,
        new_opportunities: int,
        attempt_count: int,
        error_message: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE query_expansion_variations
                SET status = ?,
                    finished_at = ?,
                    return_code = ?,
                    pipeline_status = ?,
                    collected_matches = ?,
                    new_opportunities = ?,
                    attempt_count = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (
                    status,
                    self._utc_now(),
                    return_code,
                    pipeline_status,
                    collected_matches,
                    new_opportunities,
                    attempt_count,
                    error_message,
                    variation_id,
                ),
            )

    def _finish_run(self, run_id: int) -> ExpansionSummary:
        with self._connect() as connection:
            variation_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM query_expansion_variations
                WHERE expansion_run_id = ?
                GROUP BY status
                """,
                (run_id,),
            ).fetchall()
            counts = {str(row["status"]): int(row["total"]) for row in variation_rows}
            successful = counts.get("SUCCESS", 0)
            failed = sum(
                total for status, total in counts.items() if status != "SUCCESS"
            )

            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_matches,
                    COUNT(DISTINCT opportunity_url) AS unique_opportunities
                FROM opportunity_query_matches
                WHERE expansion_run_id = ?
                """,
                (run_id,),
            ).fetchone()
            total_matches = int(totals["total_matches"])
            unique_opportunities = int(totals["unique_opportunities"])
            duplicate_matches = total_matches - unique_opportunities

            run_row = connection.execute(
                """
                SELECT original_query, variation_count
                FROM query_expansion_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            variation_count = int(run_row["variation_count"])

            if successful == variation_count:
                status = "SUCCESS"
            elif successful > 0:
                status = "PARTIAL_SUCCESS"
            else:
                status = "FAILED"

            connection.execute(
                """
                UPDATE query_expansion_runs
                SET status = ?,
                    finished_at = ?,
                    successful_variations = ?,
                    failed_variations = ?,
                    total_matches = ?,
                    unique_opportunities = ?,
                    duplicate_matches = ?
                WHERE id = ?
                """,
                (
                    status,
                    self._utc_now(),
                    successful,
                    failed,
                    total_matches,
                    unique_opportunities,
                    duplicate_matches,
                    run_id,
                ),
            )

            return ExpansionSummary(
                run_id=run_id,
                original_query=str(run_row["original_query"]),
                status=status,
                variation_count=variation_count,
                successful_variations=successful,
                failed_variations=failed,
                total_matches=total_matches,
                unique_opportunities=unique_opportunities,
                duplicate_matches=duplicate_matches,
            )

    def run(
        self,
        original_query: str,
        limit: int = 20,
        minimum_score: float = 0,
        top: int = 100,
    ) -> ExpansionSummary:
        if not (self.project_dir / "main.py").exists():
            raise FileNotFoundError(
                f"main.py not found in project directory: {self.project_dir}"
            )
        if limit < 1 or top < 1:
            raise ValueError("limit and top must be positive")

        variations = self.expander.expand(original_query)
        normalized_original = variations[0].query
        run_started_at = self._utc_now()

        precollected: dict[int, VariationExecution] = {}
        if not self._opportunities_table_exists():
            precollected[0] = self._execute_collection(
                variation=variations[0],
                total_variations=len(variations),
                limit=limit,
                minimum_score=minimum_score,
                top=top,
            )

        self._ensure_metadata_schema()
        run_id = self._create_expansion_run(
            normalized_original,
            variations,
            started_at=run_started_at,
        )

        for variation in variations:
            execution = precollected.get(variation.position)
            variation_started_at = (
                execution.started_at
                if execution is not None
                else self._utc_now()
            )
            variation_id = self._create_variation(
                run_id,
                variation,
                started_at=variation_started_at,
            )

            if execution is None:
                if variation.position > 0 and self.inter_query_delay_seconds:
                    if self.verbose:
                        print(
                            "Controle de cadência: "
                            f"{self.inter_query_delay_seconds:.0f}s antes da próxima consulta."
                        )
                    self.sleeper(self.inter_query_delay_seconds)

                execution = self._execute_collection(
                    variation=variation,
                    total_variations=len(variations),
                    limit=limit,
                    minimum_score=minimum_score,
                    top=top,
                )

            inserted_matches = self._record_matches(
                run_id=run_id,
                variation_id=variation_id,
                original_query=normalized_original,
                matched_query=variation.query,
                opportunities=execution.references,
            )

            is_success = (
                execution.result.returncode == 0
                and execution.pipeline_status == "SUCCESS"
            )
            variation_status = "SUCCESS" if is_success else execution.pipeline_status

            self._finish_variation(
                variation_id=variation_id,
                status=variation_status,
                return_code=execution.result.returncode,
                pipeline_status=execution.pipeline_status,
                collected_matches=inserted_matches,
                new_opportunities=execution.new_opportunities,
                attempt_count=execution.attempt_count,
                error_message=execution.error_message,
            )

        return self._finish_run(run_id)
