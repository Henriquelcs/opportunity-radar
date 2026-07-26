from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from src.config.credentials import Credentials


class GitHubIssuesCollector:
    """
    Coleta issues públicas do GitHub através da Search API.
    """

    API_URL = "https://api.github.com/search/issues"

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        loaded_credentials = Credentials.load()

        self.token = token or loaded_credentials.github_token
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "opportunity-radar",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    @staticmethod
    def _normalize_item(
        issue: dict[str, Any],
    ) -> dict[str, Any]:
        repository_url = issue.get("repository_url", "")
        repository = repository_url.rstrip("/").split("/")[-1]

        user = issue.get("user") or {}
        labels = issue.get("labels") or []

        return {
            "id": f"github:{issue.get('id')}",
            "external_id": issue.get("id"),
            "source": "github",
            "source_type": "issue",
            "title": issue.get("title") or "",
            "text": issue.get("body") or "",
            "url": issue.get("html_url") or "",
            "author": user.get("login") or "",
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "collected_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "repository": repository,
            "comments_count": issue.get("comments", 0),
            "score": issue.get("score", 0),
            "tags": [
                label.get("name", "")
                for label in labels
                if isinstance(label, dict)
                and label.get("name")
            ],
            "metadata": {
                "state": issue.get("state"),
                "locked": issue.get("locked", False),
                "pull_request": "pull_request" in issue,
                "repository_url": repository_url,
            },
        }

    def collect(
        self,
        limit: int = 30,
        *,
        query: str | None = None,
        language: str | None = None,
        state: str = "open",
        sort: str = "created",
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        search_terms = [
            query
            or (
                '"looking for" OR "feature request" OR '
                '"painful" OR "frustrating" OR '
                '"manual process" OR "time consuming"'
            ),
            "is:issue",
        ]

        if state:
            search_terms.append(f"state:{state}")

        if language:
            search_terms.append(f"language:{language}")

        parameters = {
            "q": " ".join(search_terms),
            "sort": sort,
            "order": order,
            "per_page": min(limit, 100),
            "page": 1,
        }

        response = self.session.get(
            self.API_URL,
            headers=self._headers(),
            params=parameters,
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()
        raw_items = payload.get("items", [])

        return [
            self._normalize_item(item)
            for item in raw_items[:limit]
            if "pull_request" not in item
        ]
