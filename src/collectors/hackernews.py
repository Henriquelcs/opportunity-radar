from __future__ import annotations

from typing import Any

import requests

from src.config.settings import (
    HACKER_NEWS_BASE_URL,
    REQUEST_TIMEOUT_SECONDS,
)


class HackerNewsCollector:
    """
    Coleta publicações públicas do Hacker News.

    Este módulo apenas coleta dados.
    Ele não filtra dores e não calcula pontuação.
    """

    def __init__(self) -> None:
        self.session = requests.Session()

    def _get_json(self, url: str) -> Any:
        """
        Executa uma requisição HTTP e retorna JSON.
        """
        response = self.session.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

        return response.json()

    def get_top_story_ids(
        self,
        limit: int,
    ) -> list[int]:
        """
        Busca os IDs das principais publicações.
        """
        if limit < 1:
            raise ValueError(
                "O limite precisa ser maior que zero."
            )

        url = (
            f"{HACKER_NEWS_BASE_URL}/"
            "topstories.json"
        )

        story_ids = self._get_json(url)

        if not isinstance(story_ids, list):
            raise RuntimeError(
                "A API retornou um formato inesperado."
            )

        return story_ids[:limit]

    def get_item(
        self,
        item_id: int,
    ) -> dict[str, Any] | None:
        """
        Busca uma publicação pelo ID.
        """
        url = (
            f"{HACKER_NEWS_BASE_URL}/"
            f"item/{item_id}.json"
        )

        try:
            item = self._get_json(url)

            if not item:
                return None

            if item.get("deleted"):
                return None

            if item.get("dead"):
                return None

            return item

        except requests.RequestException as error:
            print(
                f"Falha ao coletar item "
                f"{item_id}: {error}"
            )

            return None

    def collect(
        self,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Coleta várias publicações.
        """
        story_ids = self.get_top_story_ids(limit)

        collected_items: list[dict[str, Any]] = []

        for story_id in story_ids:
            item = self.get_item(story_id)

            if item:
                collected_items.append(item)

        return collected_items
