from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from src.storage.database import Database
from src.storage.database import (
    DEFAULT_DATABASE_PATH,
)
from src.storage.database import iter_rows


def utc_now_iso() -> str:
    """
    Retorna a data atual em UTC no formato ISO.
    """
    return datetime.now(
        timezone.utc
    ).isoformat()


def serialize_json(value: Any) -> str:
    """
    Serializa dados para armazenamento seguro.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        sort_keys=True,
    )


def deserialize_json(
    value: str | None,
    default: Any,
) -> Any:
    """
    Desserializa JSON sem interromper a aplicação.
    """
    if not value:
        return default

    try:
        return json.loads(value)
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return default


class OpportunityRepository:
    """
    Persistência de oportunidades em SQLite.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_DATABASE_PATH
        ),
    ) -> None:
        self.database = Database(
            database_path=database_path
        )

        self.database.initialize()

    @staticmethod
    def _external_id(
        item: dict[str, Any],
    ) -> str:
        """
        Resolve o identificador externo da publicação.
        """
        value = (
            item.get("external_id")
            or item.get("id")
            or item.get("url")
        )

        if value is None:
            raise ValueError(
                "Oportunidade sem id, external_id ou URL."
            )

        return str(value)

    @staticmethod
    def _source(
        item: dict[str, Any],
    ) -> str:
        """
        Resolve a fonte da oportunidade.
        """
        source = str(
            item.get("source") or ""
        ).strip()

        if not source:
            raise ValueError(
                "Oportunidade sem fonte."
            )

        return source

    def upsert(
        self,
        item: dict[str, Any],
    ) -> int:
        """
        Insere ou atualiza uma oportunidade.
        """
        now = utc_now_iso()

        external_id = self._external_id(item)
        source = self._source(item)

        values = {
            "external_id": external_id,
            "source": source,
            "title": str(
                item.get("title") or ""
            ),
            "description": str(
                item.get("description")
                or item.get("body")
                or item.get("text")
                or item.get("content")
                or ""
            ),
            "url": str(
                item.get("url") or ""
            ),
            "author": (
                str(item.get("author"))
                if item.get("author") is not None
                else None
            ),
            "published_at": (
                str(item.get("published_at"))
                if item.get("published_at")
                is not None
                else None
            ),
            "pain_categories_json": (
                serialize_json(
                    item.get(
                        "pain_categories",
                        [],
                    )
                )
            ),
            "pain_signals_json": (
                serialize_json(
                    item.get(
                        "pain_signals",
                        {},
                    )
                )
            ),
            "metadata_json": (
                serialize_json(
                    item.get(
                        "metadata",
                        {},
                    )
                )
            ),
            "pain_score": float(
                item.get("pain_score", 0) or 0
            ),
            "urgency_score": float(
                item.get("urgency_score", 0)
                or 0
            ),
            "engagement_score": float(
                item.get(
                    "engagement_score",
                    0,
                )
                or 0
            ),
            "market_score": float(
                item.get("market_score", 0)
                or 0
            ),
            "confidence_score": float(
                item.get(
                    "confidence_score",
                    0,
                )
                or 0
            ),
            "opportunity_score": float(
                item.get(
                    "opportunity_score",
                    0,
                )
                or 0
            ),
            "opportunity_level": str(
                item.get(
                    "opportunity_level",
                    "very_low",
                )
            ),
            "now": now,
        }

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO opportunities (
                    external_id,
                    source,
                    title,
                    description,
                    url,
                    author,
                    published_at,
                    pain_categories_json,
                    pain_signals_json,
                    metadata_json,
                    pain_score,
                    urgency_score,
                    engagement_score,
                    market_score,
                    confidence_score,
                    opportunity_score,
                    opportunity_level,
                    first_seen_at,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :external_id,
                    :source,
                    :title,
                    :description,
                    :url,
                    :author,
                    :published_at,
                    :pain_categories_json,
                    :pain_signals_json,
                    :metadata_json,
                    :pain_score,
                    :urgency_score,
                    :engagement_score,
                    :market_score,
                    :confidence_score,
                    :opportunity_score,
                    :opportunity_level,
                    :now,
                    :now,
                    :now,
                    :now
                )
                ON CONFLICT(
                    source,
                    external_id
                )
                DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    url = excluded.url,
                    author = excluded.author,
                    published_at = excluded.published_at,

                    pain_categories_json =
                        excluded.pain_categories_json,

                    pain_signals_json =
                        excluded.pain_signals_json,

                    metadata_json =
                        excluded.metadata_json,

                    pain_score =
                        excluded.pain_score,

                    urgency_score =
                        excluded.urgency_score,

                    engagement_score =
                        excluded.engagement_score,

                    market_score =
                        excluded.market_score,

                    confidence_score =
                        excluded.confidence_score,

                    opportunity_score =
                        excluded.opportunity_score,

                    opportunity_level =
                        excluded.opportunity_level,

                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """,
                values,
            )

            row = connection.execute(
                """
                SELECT id
                FROM opportunities
                WHERE source = ?
                  AND external_id = ?
                """,
                (
                    source,
                    external_id,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Falha ao localizar oportunidade salva."
            )

        return int(row["id"])

    def upsert_many(
        self,
        items: list[dict[str, Any]],
    ) -> int:
        """
        Insere ou atualiza várias oportunidades.
        """
        persisted_count = 0

        for item in items:
            self.upsert(item)
            persisted_count += 1

        return persisted_count

    @staticmethod
    def _hydrate(
        row: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Converte os campos JSON da linha.
        """
        hydrated = dict(row)

        hydrated["pain_categories"] = (
            deserialize_json(
                hydrated.pop(
                    "pain_categories_json",
                    None,
                ),
                [],
            )
        )

        hydrated["pain_signals"] = (
            deserialize_json(
                hydrated.pop(
                    "pain_signals_json",
                    None,
                ),
                {},
            )
        )

        hydrated["metadata"] = (
            deserialize_json(
                hydrated.pop(
                    "metadata_json",
                    None,
                ),
                {},
            )
        )

        return hydrated

    def get_by_source_and_external_id(
        self,
        source: str,
        external_id: str,
    ) -> dict[str, Any] | None:
        """
        Busca uma oportunidade pelo identificador externo.
        """
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM opportunities
                WHERE source = ?
                  AND external_id = ?
                """,
                (
                    source,
                    external_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._hydrate(dict(row))

    def list_ranked(
        self,
        limit: int = 100,
        minimum_score: float = 0.0,
        source: str | None = None,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lista oportunidades ordenadas pelo maior score.
        """
        clauses = [
            "opportunity_score >= ?"
        ]

        parameters: list[Any] = [
            float(minimum_score)
        ]

        if source:
            clauses.append("source = ?")
            parameters.append(source)

        if level:
            clauses.append(
                "opportunity_level = ?"
            )
            parameters.append(level)

        parameters.append(int(limit))

        query = f"""
            SELECT *
            FROM opportunities
            WHERE {' AND '.join(clauses)}
            ORDER BY
                opportunity_score DESC,
                confidence_score DESC,
                engagement_score DESC,
                updated_at DESC
            LIMIT ?
        """

        with self.database.connect() as connection:
            cursor = connection.execute(
                query,
                parameters,
            )

            rows = list(iter_rows(cursor))

        return [
            self._hydrate(row)
            for row in rows
        ]

    def count(self) -> int:
        """
        Retorna o total de oportunidades armazenadas.
        """
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM opportunities
                """
            ).fetchone()

        return int(row["total"])

    def delete_all(self) -> int:
        """
        Exclui todas as oportunidades.
        """
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM opportunities"
            )

            return int(cursor.rowcount)


class CollectionRunRepository:
    """
    Persiste o histórico de execuções do pipeline.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_DATABASE_PATH
        ),
    ) -> None:
        self.database = Database(
            database_path=database_path
        )

        self.database.initialize()

    def create(
        self,
        query: str,
        limit_per_source: int,
        collected_count: int,
        pain_count: int,
        opportunity_count: int,
        persisted_count: int,
        collection_errors: dict[str, str],
        started_at: str,
        finished_at: str,
        execution_status: str,
    ) -> int:
        """
        Registra uma execução do pipeline.
        """
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO collection_runs (
                    query,
                    limit_per_source,
                    collected_count,
                    pain_count,
                    opportunity_count,
                    persisted_count,
                    collection_errors_json,
                    started_at,
                    finished_at,
                    execution_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query,
                    int(limit_per_source),
                    int(collected_count),
                    int(pain_count),
                    int(opportunity_count),
                    int(persisted_count),
                    serialize_json(
                        collection_errors
                    ),
                    started_at,
                    finished_at,
                    execution_status,
                ),
            )

            return int(cursor.lastrowid)

    def list_recent(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Lista as execuções mais recentes.
        """
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM collection_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (int(limit),),
            )

            rows = list(iter_rows(cursor))

        for row in rows:
            row["collection_errors"] = (
                deserialize_json(
                    row.pop(
                        "collection_errors_json",
                        None,
                    ),
                    {},
                )
            )

        return rows
