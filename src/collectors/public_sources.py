from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable


JsonValue = dict[str, Any] | list[Any]
Transport = Callable[[str, dict[str, str]], JsonValue]


def _clean_html(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</\s*p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _utc_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    return str(value)


def _query_value(
    query: str | None = None,
    search_term: str | None = None,
    q: str | None = None,
    **kwargs: Any,
) -> str:
    candidates = (
        query,
        search_term,
        q,
        kwargs.get("term"),
        kwargs.get("keyword"),
        kwargs.get("intitle"),
        kwargs.get("_runtime_query"),
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def _normalized_item(
    *,
    source: str,
    external_id: str,
    title: Any,
    body: Any,
    url: Any,
    author: Any = "",
    created_at: Any = "",
    score: Any = 0,
    comments: Any = 0,
    answers: Any = 0,
    views: Any = 0,
    tags: Iterable[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_title = _clean_html(title)
    clean_body = _clean_html(body)
    clean_url = str(url or "").strip()
    clean_author = _clean_html(author)
    tag_values = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
    created = _utc_iso(created_at)

    return {
        "id": f"{source}:{external_id}",
        "external_id": str(external_id),
        "source_id": str(external_id),
        "source": source,
        "title": clean_title,
        "body": clean_body,
        "text": f"{clean_title}\n{clean_body}".strip(),
        "content": clean_body,
        "description": clean_body,
        "url": clean_url,
        "link": clean_url,
        "author": clean_author,
        "created_at": created,
        "published_at": created,
        "timestamp": created,
        "score": float(score or 0),
        "upvotes": float(score or 0),
        "comments": int(comments or 0),
        "comment_count": int(comments or 0),
        "answers": int(answers or 0),
        "answer_count": int(answers or 0),
        "views": int(views or 0),
        "view_count": int(views or 0),
        "tags": tag_values,
        "metadata": metadata or {},
    }


class HttpJsonClient:
    def __init__(
        self,
        *,
        timeout: float = 25.0,
        attempts: int = 3,
        user_agent: str = "OpportunityRadar/1.0",
    ) -> None:
        self.timeout = timeout
        self.attempts = max(1, attempts)
        self.user_agent = user_agent

    def get(self, url: str, headers: dict[str, str] | None = None) -> JsonValue:
        request_headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        request_headers.update(headers or {})

        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            request = urllib.request.Request(url, headers=request_headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = response.read().decode("utf-8")
                    return json.loads(payload)
            except urllib.error.HTTPError as error:
                last_error = error
                retry_after = error.headers.get("Retry-After")
                if error.code not in {429, 500, 502, 503, 504}:
                    raise
                delay = float(retry_after or min(2 ** attempt, 12))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                delay = float(min(2 ** attempt, 12))

            if attempt < self.attempts:
                time.sleep(delay)

        raise RuntimeError(f"Falha HTTP após {self.attempts} tentativas: {last_error}")


@dataclass
class StackExchangeSiteCollector:
    source: str
    site: str
    client: HttpJsonClient | None = None

    API_BASE = "https://api.stackexchange.com/2.3"

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = HttpJsonClient()
        self.name = self.source
        self._runtime_query = ""

    def collect(
        self,
        limit: int = 30,
        query: str | None = None,
        search_term: str | None = None,
        q: str | None = None,
        sort: str = "relevance",
        order: str = "desc",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        search_query = _query_value(
            query,
            search_term,
            q,
            _runtime_query=self._runtime_query,
            **kwargs,
        )
        page_size = max(1, min(int(limit), 100))
        endpoint = "search/advanced" if search_query else "questions"
        params: dict[str, str] = {
            "site": self.site,
            "pagesize": str(page_size),
            "order": order,
            "sort": sort if search_query else "activity",
            "filter": "withbody",
        }
        if search_query:
            params["q"] = search_query

        api_key = os.getenv("STACKEXCHANGE_KEY", "").strip()
        if api_key:
            params["key"] = api_key

        url = f"{self.API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
        payload = self.client.get(url)
        if not isinstance(payload, dict):
            raise TypeError(f"Resposta inválida do Stack Exchange para {self.site}.")

        backoff = payload.get("backoff")
        if backoff:
            time.sleep(float(backoff))

        items = payload.get("items", [])
        if not isinstance(items, list):
            raise TypeError("Campo items inválido na resposta do Stack Exchange.")

        normalized: list[dict[str, Any]] = []
        for item in items[:page_size]:
            if not isinstance(item, dict):
                continue
            owner = item.get("owner") or {}
            normalized.append(
                _normalized_item(
                    source=self.source,
                    external_id=str(item.get("question_id", "")),
                    title=item.get("title", ""),
                    body=item.get("body", ""),
                    url=item.get("link", ""),
                    author=owner.get("display_name", "") if isinstance(owner, dict) else "",
                    created_at=item.get("creation_date"),
                    score=item.get("score", 0),
                    comments=item.get("comment_count", 0),
                    answers=item.get("answer_count", 0),
                    views=item.get("view_count", 0),
                    tags=item.get("tags", []),
                    metadata={
                        "site": self.site,
                        "is_answered": bool(item.get("is_answered", False)),
                        "accepted_answer_id": item.get("accepted_answer_id"),
                    },
                )
            )
        return normalized


class SoftwareRecommendationsCollector(StackExchangeSiteCollector):
    def __init__(self, client: HttpJsonClient | None = None) -> None:
        super().__init__(
            source="softwarerecs",
            site="softwarerecs",
            client=client,
        )


class WebApplicationsCollector(StackExchangeSiteCollector):
    def __init__(self, client: HttpJsonClient | None = None) -> None:
        super().__init__(
            source="webapps",
            site="webapps",
            client=client,
        )


class HackerNewsCollector:
    source = "hackernews"
    name = source
    API_BASE = "https://hacker-news.firebaseio.com/v0"
    STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "automation", "be", "by",
        "for", "from", "how", "in", "is", "it", "of", "on", "or", "the",
        "to", "with", "workflow",
    }

    def __init__(self, client: HttpJsonClient | None = None) -> None:
        self.client = client or HttpJsonClient()
        self._runtime_query = ""

    def _matches(self, item: dict[str, Any], query: str) -> bool:
        if not query:
            return True
        tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", query.casefold())
            if len(token) >= 3 and token not in self.STOPWORDS
        }
        if not tokens:
            return True
        searchable = _clean_html(
            f"{item.get('title', '')} {item.get('text', '')}"
        ).casefold()
        return any(token in searchable for token in tokens)

    def collect(
        self,
        limit: int = 30,
        query: str | None = None,
        search_term: str | None = None,
        q: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        search_query = _query_value(
            query,
            search_term,
            q,
            _runtime_query=self._runtime_query,
            **kwargs,
        )
        ids_payload = self.client.get(f"{self.API_BASE}/askstories.json")
        if not isinstance(ids_payload, list):
            raise TypeError("Resposta inválida de askstories do Hacker News.")

        requested = max(1, int(limit))
        scan_size = min(len(ids_payload), max(80, requested * 8))
        candidate_ids = [int(value) for value in ids_payload[:scan_size]]

        items_by_id: dict[int, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_map = {
                executor.submit(
                    self.client.get,
                    f"{self.API_BASE}/item/{item_id}.json",
                ): item_id
                for item_id in candidate_ids
            }
            for future in as_completed(future_map):
                item_id = future_map[future]
                payload = future.result()
                if isinstance(payload, dict):
                    items_by_id[item_id] = payload

        normalized: list[dict[str, Any]] = []
        for item_id in candidate_ids:
            item = items_by_id.get(item_id)
            if not item or item.get("deleted") or item.get("dead"):
                continue
            if item.get("type") != "story":
                continue
            if not str(item.get("title", "")).casefold().startswith("ask hn"):
                continue
            if not self._matches(item, search_query):
                continue

            normalized.append(
                _normalized_item(
                    source=self.source,
                    external_id=str(item.get("id", item_id)),
                    title=item.get("title", ""),
                    body=item.get("text", ""),
                    url=f"https://news.ycombinator.com/item?id={item_id}",
                    author=item.get("by", ""),
                    created_at=item.get("time"),
                    score=item.get("score", 0),
                    comments=item.get("descendants", 0),
                    metadata={"item_type": item.get("type", "story")},
                )
            )
            if len(normalized) >= requested:
                break

        return normalized


class DevCommunityCollector:
    source = "devto"
    name = source
    API_BASE = "https://dev.to/api"

    def __init__(self, client: HttpJsonClient | None = None) -> None:
        self.client = client or HttpJsonClient()
        self._runtime_query = ""
        self.headers = {"Accept": "application/vnd.forem.api-v1+json"}

    def collect(
        self,
        limit: int = 30,
        query: str | None = None,
        search_term: str | None = None,
        q: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        search_query = _query_value(
            query,
            search_term,
            q,
            _runtime_query=self._runtime_query,
            **kwargs,
        )
        page_size = max(1, min(int(limit), 100))
        if search_query:
            params = urllib.parse.urlencode(
                {"q": search_query, "page": 1, "per_page": page_size}
            )
            url = f"{self.API_BASE}/articles/search?{params}"
        else:
            params = urllib.parse.urlencode(
                {"state": "fresh", "page": 1, "per_page": page_size}
            )
            url = f"{self.API_BASE}/articles?{params}"

        payload = self.client.get(url, self.headers)
        if not isinstance(payload, list):
            raise TypeError("Resposta inválida da API do DEV Community.")

        summaries = [item for item in payload[:page_size] if isinstance(item, dict)]
        details: dict[int, dict[str, Any]] = {}

        def load_detail(article_id: int) -> tuple[int, dict[str, Any]]:
            detail = self.client.get(
                f"{self.API_BASE}/articles/{article_id}",
                self.headers,
            )
            return article_id, detail if isinstance(detail, dict) else {}

        with ThreadPoolExecutor(max_workers=6) as executor:
            future_map = {
                executor.submit(load_detail, int(item["id"])): int(item["id"])
                for item in summaries
                if item.get("id") is not None
            }
            for future in as_completed(future_map):
                article_id, detail = future.result()
                details[article_id] = detail

        normalized: list[dict[str, Any]] = []
        for summary in summaries:
            article_id = int(summary.get("id", 0))
            detail = details.get(article_id, {})
            user = detail.get("user") or summary.get("user") or {}
            body = (
                detail.get("body_markdown")
                or detail.get("body_html")
                or summary.get("description")
                or ""
            )
            tags = (
                detail.get("tag_list")
                or summary.get("tag_list")
                or summary.get("tags")
                or []
            )
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

            normalized.append(
                _normalized_item(
                    source=self.source,
                    external_id=str(article_id),
                    title=detail.get("title") or summary.get("title", ""),
                    body=body,
                    url=detail.get("url") or summary.get("url", ""),
                    author=user.get("name", "") if isinstance(user, dict) else "",
                    created_at=(
                        detail.get("published_at")
                        or summary.get("published_at")
                        or summary.get("published_timestamp")
                    ),
                    score=(
                        detail.get("public_reactions_count")
                        or summary.get("public_reactions_count")
                        or 0
                    ),
                    comments=(
                        detail.get("comments_count")
                        or summary.get("comments_count")
                        or 0
                    ),
                    tags=tags,
                    metadata={
                        "reading_time_minutes": (
                            detail.get("reading_time_minutes")
                            or summary.get("reading_time_minutes")
                        ),
                        "type_of": summary.get("type_of", "article"),
                    },
                )
            )
        return normalized


def build_new_collectors() -> list[Any]:
    return [
        SoftwareRecommendationsCollector(),
        WebApplicationsCollector(),
        HackerNewsCollector(),
        DevCommunityCollector(),
    ]


__all__ = [
    "DevCommunityCollector",
    "HackerNewsCollector",
    "HttpJsonClient",
    "SoftwareRecommendationsCollector",
    "StackExchangeSiteCollector",
    "WebApplicationsCollector",
    "build_new_collectors",
]
