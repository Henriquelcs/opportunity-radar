from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests


class StackOverflowCollector:
    """
    Coleta perguntas públicas através da Stack Exchange API.
    """

    API_URL = (
        "https://api.stackexchange.com/2.3/questions"
    )

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

    @staticmethod
    def _to_iso_timestamp(
        value: int | float | None,
    ) -> str | None:
        if value is None:
            return None

        return datetime.fromtimestamp(
            value,
            tz=timezone.utc,
        ).isoformat()

    @classmethod
    def _normalize_item(
        cls,
        question: dict[str, Any],
    ) -> dict[str, Any]:
        owner = question.get("owner") or {}

        return {
            "id": (
                f"stackoverflow:"
                f"{question.get('question_id')}"
            ),
            "external_id": question.get("question_id"),
            "source": "stackoverflow",
            "source_type": "question",
            "title": question.get("title") or "",
            "text": question.get("body") or "",
            "url": question.get("link") or "",
            "author": owner.get("display_name") or "",
            "created_at": cls._to_iso_timestamp(
                question.get("creation_date")
            ),
            "updated_at": cls._to_iso_timestamp(
                question.get("last_activity_date")
            ),
            "collected_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "tags": question.get("tags") or [],
            "score": question.get("score", 0),
            "comments_count": question.get(
                "answer_count",
                0,
            ),
            "metadata": {
                "view_count": question.get(
                    "view_count",
                    0,
                ),
                "answer_count": question.get(
                    "answer_count",
                    0,
                ),
                "is_answered": question.get(
                    "is_answered",
                    False,
                ),
                "accepted_answer_id": question.get(
                    "accepted_answer_id"
                ),
                "owner_reputation": owner.get(
                    "reputation"
                ),
            },
        }

    def collect(
        self,
        limit: int = 30,
        *,
        tagged: str | list[str] | None = None,
        search_term: str | None = None,
        sort: str = "creation",
        order: str = "desc",
        site: str = "stackoverflow",
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        parameters: dict[str, Any] = {
            "site": site,
            "pagesize": min(limit, 100),
            "page": 1,
            "sort": sort,
            "order": order,
            "filter": "withbody",
        }

        if tagged:
            if isinstance(tagged, list):
                parameters["tagged"] = ";".join(tagged)
            else:
                parameters["tagged"] = tagged

        if search_term:
            parameters["intitle"] = search_term

        response = self.session.get(
            self.API_URL,
            params=parameters,
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()

        if payload.get("error_id"):
            raise RuntimeError(
                payload.get(
                    "error_message",
                    "Erro na Stack Exchange API.",
                )
            )

        return [
            self._normalize_item(item)
            for item in payload.get("items", [])[:limit]
        ]
