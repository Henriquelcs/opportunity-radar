from __future__ import annotations

import html
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urlparse

import requests

from src.cache.source_cache import SourceCache, SourceSnapshot, parse_utc, utc_iso, utc_now


SOURCE_ORDER = (
    "github",
    "stackoverflow",
    "softwarerecs",
    "webapps",
    "hackernews",
    "devto",
)


def _strip_html(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _iso_from_epoch(value: Any) -> str:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat(
            timespec="seconds"
        )
    except (TypeError, ValueError, OSError):
        return ""


def _normalize_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def normalized_item(
    *,
    source: str,
    external_id: Any,
    title: Any,
    description: Any,
    url: Any,
    author: Any = "",
    published_at: Any = "",
    tags: Any = None,
    engagement: Any = 0,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        numeric_engagement = float(engagement or 0)
    except (TypeError, ValueError):
        numeric_engagement = 0.0
    return {
        "source": str(source).strip(),
        "external_id": str(external_id).strip(),
        "title": _strip_html(title),
        "description": _strip_html(description),
        "url": str(url or "").strip(),
        "author": str(author or "").strip(),
        "published_at": str(published_at or "").strip(),
        "tags": _normalize_tags(tags),
        "engagement": max(0.0, numeric_engagement),
        "metadata": metadata or {},
    }


class RateLimitError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int = 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(1, int(retry_after_seconds))


class HttpJsonClient:
    """HTTP JSON com retry apenas para falhas transitórias; 429 vira cooldown."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 25,
        max_attempts: int = 2,
        session: requests.Session | None = None,
        sleeper=time.sleep,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self.session = session or requests.Session()
        self.sleeper = sleeper

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> int:
        raw = str(response.headers.get("Retry-After", "") or "").strip()
        if not raw:
            return 60
        try:
            return max(1, int(float(raw)))
        except ValueError:
            try:
                target = parsedate_to_datetime(raw)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                return max(
                    1,
                    int((target.astimezone(timezone.utc) - utc_now()).total_seconds()),
                )
            except (TypeError, ValueError, OverflowError):
                return 60

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        host_path = f"{urlparse(url).netloc}{urlparse(url).path}"
        for attempt in range(1, self.max_attempts + 1):
            print(f"[HTTP] GET {host_path} tentativa={attempt}/{self.max_attempts}")
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 429:
                retry_after = self._retry_after_seconds(response)
                raise RateLimitError(
                    f"HTTP 429 em {host_path}; Retry-After={retry_after}s",
                    retry_after,
                )
            if 500 <= response.status_code < 600 and attempt < self.max_attempts:
                delay = min(8, 2 ** (attempt - 1))
                print(
                    f"[HTTP] {response.status_code} em {host_path}; "
                    f"novo intento em {delay}s"
                )
                self.sleeper(delay)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"Falha HTTP sem resposta válida em {host_path}")


class SnapshotCollector(Protocol):
    source: str

    def collect(
        self,
        *,
        limit: int,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        ...


class GitHubSnapshotCollector:
    source = "github"

    def __init__(
        self,
        client: HttpJsonClient,
        token: str | None = None,
    ) -> None:
        self.client = client
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    def collect(
        self,
        *,
        limit: int,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            "is:issue state:open "
            "(manual OR repetitive OR workaround OR automation OR \"time consuming\")"
        )
        if since:
            query += f" updated:>={parse_utc(since).date().isoformat()}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "opportunity-radar",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = self.client.get_json(
            "https://api.github.com/search/issues",
            params={
                "q": query,
                "sort": "updated",
                "order": "desc",
                "per_page": min(max(1, limit), 100),
            },
            headers=headers,
        )
        items: list[dict[str, Any]] = []
        for raw in payload.get("items", []) if isinstance(payload, dict) else []:
            repository_url = str(raw.get("repository_url", "") or "")
            repository = repository_url.rsplit("/", 1)[-1] if repository_url else ""
            items.append(
                normalized_item(
                    source=self.source,
                    external_id=raw.get("id"),
                    title=raw.get("title"),
                    description=raw.get("body"),
                    url=raw.get("html_url"),
                    author=(raw.get("user") or {}).get("login"),
                    published_at=raw.get("created_at"),
                    tags=[label.get("name") for label in raw.get("labels", [])],
                    engagement=float(raw.get("comments", 0) or 0)
                    + float((raw.get("reactions") or {}).get("total_count", 0) or 0),
                    metadata={
                        "repository": repository,
                        "updated_at": raw.get("updated_at"),
                        "state": raw.get("state"),
                    },
                )
            )
        return [item for item in items if item["external_id"]]


class StackExchangeSnapshotCollector:
    API_URL = "https://api.stackexchange.com/2.3/questions"

    def __init__(
        self,
        client: HttpJsonClient,
        *,
        source: str,
        site: str,
        key: str | None = None,
    ) -> None:
        self.client = client
        self.source = source
        self.site = site
        self.key = key or os.getenv("STACKEXCHANGE_KEY")

    def collect(
        self,
        *,
        limit: int,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "site": self.site,
            "pagesize": min(max(1, limit), 100),
            "page": 1,
            "order": "desc",
            "sort": "activity",
            "filter": "withbody",
        }
        if self.key:
            params["key"] = self.key
        if since:
            params["fromdate"] = int(parse_utc(since).timestamp())
        payload = self.client.get_json(self.API_URL, params=params)
        if isinstance(payload, dict) and payload.get("backoff"):
            raise RateLimitError(
                f"Stack Exchange solicitou backoff para {self.site}",
                int(payload["backoff"]),
            )
        items: list[dict[str, Any]] = []
        for raw in payload.get("items", []) if isinstance(payload, dict) else []:
            items.append(
                normalized_item(
                    source=self.source,
                    external_id=raw.get("question_id"),
                    title=raw.get("title"),
                    description=raw.get("body"),
                    url=raw.get("link"),
                    author=(raw.get("owner") or {}).get("display_name"),
                    published_at=_iso_from_epoch(raw.get("creation_date")),
                    tags=raw.get("tags"),
                    engagement=float(raw.get("score", 0) or 0)
                    + float(raw.get("answer_count", 0) or 0)
                    + math.log1p(float(raw.get("view_count", 0) or 0)),
                    metadata={
                        "site": self.site,
                        "is_answered": raw.get("is_answered"),
                        "last_activity_date": _iso_from_epoch(
                            raw.get("last_activity_date")
                        ),
                    },
                )
            )
        return [item for item in items if item["external_id"]]


class DevCommunitySnapshotCollector:
    source = "devto"

    def __init__(
        self,
        client: HttpJsonClient,
        api_key: str | None = None,
    ) -> None:
        self.client = client
        self.api_key = api_key or os.getenv("DEVTO_API_KEY")

    def collect(
        self,
        *,
        limit: int,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        del since
        headers = {
            "Accept": "application/vnd.forem.api-v1+json",
            "User-Agent": "opportunity-radar",
        }
        if self.api_key:
            headers["api-key"] = self.api_key
        payload = self.client.get_json(
            "https://dev.to/api/articles",
            params={
                "page": 1,
                "per_page": min(max(1, limit), 100),
                "state": "fresh",
            },
            headers=headers,
        )
        items: list[dict[str, Any]] = []
        for raw in payload if isinstance(payload, list) else []:
            user = raw.get("user") or {}
            items.append(
                normalized_item(
                    source=self.source,
                    external_id=raw.get("id"),
                    title=raw.get("title"),
                    description=raw.get("description"),
                    url=raw.get("url"),
                    author=user.get("username") or user.get("name"),
                    published_at=raw.get("published_at"),
                    tags=raw.get("tag_list"),
                    engagement=float(raw.get("positive_reactions_count", 0) or 0)
                    + float(raw.get("comments_count", 0) or 0),
                    metadata={
                        "reading_time_minutes": raw.get("reading_time_minutes"),
                        "public_reactions_count": raw.get("public_reactions_count"),
                        "edited_at": raw.get("edited_at"),
                    },
                )
            )
        return [item for item in items if item["external_id"]]


class HackerNewsSnapshotCollector:
    source = "hackernews"
    ASK_STORIES_URL = (
        "https://hacker-news.firebaseio.com/v0/askstories.json"
    )
    ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"

    def __init__(
        self,
        client: HttpJsonClient,
        cache: SourceCache,
        *,
        item_cache_ttl_seconds: int = 7 * 24 * 60 * 60,
        max_workers: int = 8,
    ) -> None:
        self.client = client
        self.cache = cache
        self.item_cache_ttl_seconds = item_cache_ttl_seconds
        self.max_workers = max(1, max_workers)

    def _load_item(self, item_id: str) -> dict[str, Any] | None:
        cached = self.cache.get_item(
            self.source,
            item_id,
            max_age_seconds=self.item_cache_ttl_seconds,
        )
        if cached is not None:
            return cached
        raw = self.client.get_json(self.ITEM_URL.format(item_id=item_id))
        if not isinstance(raw, dict) or raw.get("deleted") or raw.get("dead"):
            return None
        item = normalized_item(
            source=self.source,
            external_id=raw.get("id"),
            title=raw.get("title"),
            description=raw.get("text"),
            url=raw.get("url") or f"https://news.ycombinator.com/item?id={raw.get('id')}",
            author=raw.get("by"),
            published_at=_iso_from_epoch(raw.get("time")),
            tags=["Ask HN"],
            engagement=float(raw.get("score", 0) or 0)
            + float(raw.get("descendants", 0) or 0),
            metadata={"type": raw.get("type"), "kids": raw.get("kids", [])},
        )
        if item["external_id"]:
            self.cache.upsert_items(self.source, [item])
            return item
        return None

    def collect(
        self,
        *,
        limit: int,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        del since
        ids = self.client.get_json(self.ASK_STORIES_URL)
        if not isinstance(ids, list):
            return []
        scan_count = min(len(ids), max(12, min(50, limit * 3)))
        candidates = [str(item_id) for item_id in ids[:scan_count]]
        items: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._load_item, item_id): item_id
                for item_id in candidates
            }
            for future in as_completed(futures):
                try:
                    item = future.result()
                except RateLimitError:
                    raise
                except Exception as exc:
                    print(
                        f"[WARN] Hacker News item={futures[future]} ignorado: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    continue
                if item is not None:
                    items.append(item)
        items.sort(
            key=lambda item: str(item.get("published_at", "")),
            reverse=True,
        )
        return items[: max(1, limit)]


@dataclass(frozen=True)
class SourceSyncState:
    source: str
    status: str
    item_count: int
    new_item_count: int
    snapshot_at: str
    error: str = ""
    retry_after_seconds: int = 0


@dataclass(frozen=True)
class SnapshotSyncResult:
    status: str
    items: list[dict[str, Any]]
    sources: dict[str, SourceSyncState]

    @property
    def errors(self) -> dict[str, str]:
        return {
            source: state.error
            for source, state in self.sources.items()
            if state.error
        }


class SnapshotSynchronizer:
    """Sincroniza cada fonte uma única vez e consolida o snapshot local."""

    def __init__(
        self,
        cache: SourceCache,
        collectors: list[SnapshotCollector],
        *,
        max_snapshot_items: int = 500,
    ) -> None:
        self.cache = cache
        self.collectors = collectors
        self.max_snapshot_items = max(1, max_snapshot_items)
        names = [collector.source for collector in collectors]
        if len(names) != len(set(names)):
            raise ValueError("Coletores duplicados no mesmo ciclo")

    @staticmethod
    def _merge_items(
        previous: list[dict[str, Any]],
        current: list[dict[str, Any]],
        *,
        maximum: int,
    ) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for item in previous:
            key = (
                str(item.get("source", "")),
                str(item.get("external_id", "")),
            )
            if all(key):
                merged[key] = item
        for item in current:
            key = (
                str(item.get("source", "")),
                str(item.get("external_id", "")),
            )
            if all(key):
                merged[key] = item
        values = list(merged.values())
        values.sort(
            key=lambda item: str(item.get("published_at", "")),
            reverse=True,
        )
        return values[:maximum]

    def _fallback_state(
        self,
        collector: SnapshotCollector,
        previous: SourceSnapshot | None,
        *,
        error: str,
        retry_after_seconds: int = 0,
    ) -> tuple[list[dict[str, Any]], SourceSyncState]:
        if previous and previous.items:
            print(
                f"[CACHE] {collector.source}: usando snapshot anterior "
                f"com {len(previous.items)} itens"
            )
            return previous.items, SourceSyncState(
                source=collector.source,
                status="CACHE",
                item_count=len(previous.items),
                new_item_count=0,
                snapshot_at=previous.fetched_at,
                error=error,
                retry_after_seconds=retry_after_seconds,
            )
        print(f"[DEGRADED] {collector.source}: indisponível e sem cache")
        return [], SourceSyncState(
            source=collector.source,
            status="UNAVAILABLE",
            item_count=0,
            new_item_count=0,
            snapshot_at=utc_iso(),
            error=error,
            retry_after_seconds=retry_after_seconds,
        )

    def sync(self, *, limit_per_source: int) -> SnapshotSyncResult:
        all_items: list[dict[str, Any]] = []
        states: dict[str, SourceSyncState] = {}
        print(
            f"[SYNC] início: fontes={len(self.collectors)} "
            f"limite_por_fonte={limit_per_source}"
        )
        for collector in self.collectors:
            source = collector.source
            previous = self.cache.latest_snapshot(source)
            cooldown = self.cache.cooldown_remaining(source)
            if cooldown > 0:
                items, state = self._fallback_state(
                    collector,
                    previous,
                    error=f"Cooldown ativo; nova tentativa permitida em {cooldown}s",
                    retry_after_seconds=cooldown,
                )
                all_items.extend(items)
                states[source] = state
                continue
            print(f"[SYNC] {source}: coleta externa única")
            try:
                current = collector.collect(
                    limit=limit_per_source,
                    since=previous.fetched_at if previous else None,
                )
                merged = self._merge_items(
                    previous.items if previous else [],
                    current,
                    maximum=self.max_snapshot_items,
                )
                timestamp = utc_iso()
                self.cache.upsert_items(source, current, fetched_at=timestamp)
                snapshot = self.cache.save_snapshot(
                    source,
                    merged,
                    status="LIVE",
                    fetched_at=timestamp,
                )
                self.cache.clear_cooldown(source)
                state = SourceSyncState(
                    source=source,
                    status="LIVE",
                    item_count=len(merged),
                    new_item_count=len(current),
                    snapshot_at=snapshot.fetched_at,
                )
                print(
                    f"[SYNC] {source}: LIVE novos={len(current)} "
                    f"snapshot={len(merged)}"
                )
                all_items.extend(merged)
                states[source] = state
            except RateLimitError as exc:
                blocked_until = self.cache.set_cooldown(
                    source,
                    exc.retry_after_seconds,
                    reason=str(exc),
                )
                error = f"{exc}; bloqueado até {blocked_until}"
                items, state = self._fallback_state(
                    collector,
                    previous,
                    error=error,
                    retry_after_seconds=exc.retry_after_seconds,
                )
                all_items.extend(items)
                states[source] = state
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                items, state = self._fallback_state(
                    collector,
                    previous,
                    error=error,
                )
                all_items.extend(items)
                states[source] = state
        if not all_items:
            status = "FAILED"
        elif all(state.status == "LIVE" for state in states.values()):
            status = "SUCCESS"
        else:
            status = "DEGRADED"
        print(
            f"[SYNC] fim: status={status} itens_reutilizáveis={len(all_items)}"
        )
        return SnapshotSyncResult(
            status=status,
            items=all_items,
            sources=states,
        )


def build_default_collectors(
    cache: SourceCache,
    *,
    client: HttpJsonClient | None = None,
) -> list[SnapshotCollector]:
    http = client or HttpJsonClient()
    stack_key = os.getenv("STACKEXCHANGE_KEY")
    return [
        GitHubSnapshotCollector(http),
        StackExchangeSnapshotCollector(
            http,
            source="stackoverflow",
            site="stackoverflow",
            key=stack_key,
        ),
        StackExchangeSnapshotCollector(
            http,
            source="softwarerecs",
            site="softwarerecs",
            key=stack_key,
        ),
        StackExchangeSnapshotCollector(
            http,
            source="webapps",
            site="webapps",
            key=stack_key,
        ),
        HackerNewsSnapshotCollector(http, cache),
        DevCommunitySnapshotCollector(http),
    ]
