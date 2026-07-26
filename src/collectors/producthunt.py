from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests

from src.config.credentials import Credentials


class ProductHuntCollector:
    """
    Coleta lançamentos através da Product Hunt GraphQL API.
    """

    TOKEN_URL = (
        "https://api.producthunt.com/v2/oauth/token"
    )
    GRAPHQL_URL = (
        "https://api.producthunt.com/v2/api/graphql"
    )

    POSTS_QUERY = """
    query OpportunityRadarPosts(
        $first: Int!,
        $after: String,
        $order: PostsOrder
    ) {
      posts(
        first: $first,
        after: $after,
        order: $order
      ) {
        edges {
          node {
            id
            name
            tagline
            description
            url
            website
            createdAt
            votesCount
            commentsCount
            topics {
              edges {
                node {
                  name
                }
              }
            }
            user {
              username
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        *,
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        loaded_credentials = Credentials.load()

        self.api_key = (
            api_key
            or loaded_credentials.producthunt_api_key
        )
        self.api_secret = (
            api_secret
            or loaded_credentials.producthunt_api_secret
        )
        self.timeout = timeout
        self.session = session or requests.Session()

        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def _validate_credentials(self) -> None:
        if not self.api_key or not self.api_secret:
            raise RuntimeError(
                "PRODUCTHUNT_API_KEY e "
                "PRODUCTHUNT_API_SECRET são obrigatórios."
            )

    def _request_access_token(self) -> str:
        self._validate_credentials()

        response = self.session.post(
            self.TOKEN_URL,
            json={
                "client_id": self.api_key,
                "client_secret": self.api_secret,
                "grant_type": "client_credentials",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "opportunity-radar",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()
        access_token = payload.get("access_token")

        if not access_token:
            raise RuntimeError(
                "A Product Hunt não retornou access_token."
            )

        expires_in = int(payload.get("expires_in", 3600))

        self._access_token = access_token
        self._token_expires_at = (
            time.time() + max(expires_in - 60, 60)
        )

        return access_token

    def _get_access_token(self) -> str:
        if (
            self._access_token
            and time.time() < self._token_expires_at
        ):
            return self._access_token

        return self._request_access_token()

    @staticmethod
    def _normalize_item(
        post: dict[str, Any],
    ) -> dict[str, Any]:
        topics_data = post.get("topics") or {}
        topic_edges = topics_data.get("edges") or []

        topics = []

        for edge in topic_edges:
            node = edge.get("node") or {}
            name = node.get("name")

            if name:
                topics.append(name)

        user = post.get("user") or {}

        description_parts = [
            post.get("tagline"),
            post.get("description"),
        ]

        text = " ".join(
            part.strip()
            for part in description_parts
            if isinstance(part, str) and part.strip()
        )

        return {
            "id": f"producthunt:{post.get('id')}",
            "external_id": post.get("id"),
            "source": "producthunt",
            "source_type": "product",
            "title": post.get("name") or "",
            "text": text,
            "url": (
                post.get("url")
                or post.get("website")
                or ""
            ),
            "author": user.get("username") or "",
            "created_at": post.get("createdAt"),
            "updated_at": None,
            "collected_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "tags": topics,
            "score": post.get("votesCount", 0),
            "comments_count": post.get(
                "commentsCount",
                0,
            ),
            "metadata": {
                "tagline": post.get("tagline"),
                "description": post.get("description"),
                "website": post.get("website"),
                "votes_count": post.get(
                    "votesCount",
                    0,
                ),
                "comments_count": post.get(
                    "commentsCount",
                    0,
                ),
            },
        }

    def collect(
        self,
        limit: int = 30,
        *,
        order: str = "NEWEST",
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        access_token = self._get_access_token()

        response = self.session.post(
            self.GRAPHQL_URL,
            json={
                "query": self.POSTS_QUERY,
                "variables": {
                    "first": min(limit, 100),
                    "after": None,
                    "order": order,
                },
            },
            headers={
                "Authorization": (
                    f"Bearer {access_token}"
                ),
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "opportunity-radar",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()

        if payload.get("errors"):
            error_messages = [
                error.get("message", "Erro GraphQL")
                for error in payload["errors"]
            ]

            raise RuntimeError(
                "Product Hunt GraphQL: "
                + "; ".join(error_messages)
            )

        posts_data = (
            payload.get("data", {}).get("posts", {})
        )
        edges = posts_data.get("edges", [])

        return [
            self._normalize_item(edge.get("node") or {})
            for edge in edges[:limit]
            if edge.get("node")
        ]
