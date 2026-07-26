from __future__ import annotations

from dataclasses import dataclass

from src.collectors.multisource_patch import (
    extend_collection_result,
    extract_call_context,
    patch_manager_class,
)
from src.collectors.public_sources import (
    DevCommunityCollector,
    HackerNewsCollector,
    SoftwareRecommendationsCollector,
    WebApplicationsCollector,
)


class FakeClient:
    def get(self, url: str, headers: dict[str, str] | None = None):
        if "askstories.json" in url:
            return [101]
        if "/item/101.json" in url:
            return {
                "id": 101,
                "type": "story",
                "title": "Ask HN: How do you automate manual reports?",
                "text": "We repeat this task every week.",
                "by": "tester",
                "time": 1_700_000_000,
                "score": 15,
                "descendants": 4,
            }
        if "api.stackexchange.com" in url:
            return {
                "items": [
                    {
                        "question_id": 55,
                        "title": "Automate repetitive spreadsheet updates",
                        "body": "<p>I need software for this manual process.</p>",
                        "link": "https://example.test/q/55",
                        "creation_date": 1_700_000_000,
                        "score": 3,
                        "answer_count": 2,
                        "view_count": 90,
                        "tags": ["automation"],
                        "owner": {"display_name": "User"},
                    }
                ]
            }
        if "/api/articles/search" in url or "/api/articles?" in url:
            return [
                {
                    "id": 77,
                    "title": "How can I automate this workflow?",
                    "description": "This manual process wastes time.",
                    "url": "https://dev.to/test/article",
                    "published_at": "2026-01-01T00:00:00Z",
                    "comments_count": 2,
                    "public_reactions_count": 5,
                    "tag_list": ["help"],
                    "user": {"name": "Developer"},
                }
            ]
        if "/api/articles/77" in url:
            return {
                "id": 77,
                "title": "How can I automate this workflow?",
                "body_markdown": "This manual process wastes time.",
                "url": "https://dev.to/test/article",
                "published_at": "2026-01-01T00:00:00Z",
                "comments_count": 2,
                "public_reactions_count": 5,
                "tag_list": ["help"],
                "user": {"name": "Developer"},
            }
        raise AssertionError(f"URL inesperada: {url}")


def test_stackexchange_collectors_use_distinct_sources():
    client = FakeClient()
    software = SoftwareRecommendationsCollector(client=client).collect(
        query="spreadsheet automation",
        limit=5,
    )
    webapps = WebApplicationsCollector(client=client).collect(
        query="spreadsheet automation",
        limit=5,
    )

    assert software[0]["source"] == "softwarerecs"
    assert webapps[0]["source"] == "webapps"
    assert software[0]["body"] == "I need software for this manual process."


def test_hackernews_collects_ask_hn_and_filters_locally():
    items = HackerNewsCollector(client=FakeClient()).collect(
        query="manual reports",
        limit=5,
    )

    assert len(items) == 1
    assert items[0]["source"] == "hackernews"
    assert items[0]["url"].endswith("item?id=101")


def test_dev_community_loads_article_detail():
    items = DevCommunityCollector(client=FakeClient()).collect(
        query="workflow automation",
        limit=5,
    )

    assert len(items) == 1
    assert items[0]["source"] == "devto"
    assert "wastes time" in items[0]["body"]


def test_extract_call_context_reads_nested_collector_options():
    def collect_all(limit=30, collector_options=None):
        return []

    query, limit = extract_call_context(
        collect_all,
        (),
        {
            "limit": 12,
            "collector_options": {
                "github": {"query": "manual data entry"}
            },
        },
    )

    assert query == "manual data entry"
    assert limit == 12


def test_extend_collection_result_supports_list():
    result = [{"source": "github"}]
    extended = extend_collection_result(
        result,
        [{"source": "devto"}],
        {},
    )

    assert [item["source"] for item in extended] == ["github", "devto"]


def test_extend_collection_result_supports_tuple():
    result = ([{"source": "github"}], {})
    extended = extend_collection_result(
        result,
        [{"source": "webapps"}],
        {"devto": "failed"},
    )

    assert len(extended[0]) == 2
    assert extended[1]["devto"] == "failed"


@dataclass(frozen=True)
class Batch:
    items: list[dict]
    errors: dict[str, str]


def test_extend_collection_result_supports_dataclass():
    result = Batch(items=[{"source": "github"}], errors={})
    extended = extend_collection_result(
        result,
        [{"source": "hackernews"}],
        {},
    )

    assert len(extended.items) == 2

class StubCollector:
    def __init__(self, source: str, items: list[dict]) -> None:
        self.source = source
        self.name = source
        self.items = items

    def collect(self, **kwargs):
        return list(self.items)


class ExplicitCollectorManager:
    def __init__(self, collectors=None) -> None:
        self.collectors = collectors or {}

    def collect_all(self, **kwargs):
        return [
            item
            for collector in self.collectors.values()
            for item in collector.collect(**kwargs)
        ]


def test_patch_preserves_explicit_collector_registry(monkeypatch):
    forbidden_calls: list[str] = []

    class ForbiddenCollector:
        source = "forbidden"
        name = source

        def collect(self, **kwargs):
            forbidden_calls.append("called")
            return [{"source": self.source}]

    monkeypatch.setattr(
        "src.collectors.multisource_patch.build_new_collectors",
        lambda: [ForbiddenCollector()],
    )

    patch_manager_class(ExplicitCollectorManager)

    manager = ExplicitCollectorManager(
        collectors={
            "custom": StubCollector(
                "custom",
                [{"source": "custom", "id": "custom:1"}],
            )
        }
    )
    result = manager.collect_all(limit=5)

    assert result == [{"source": "custom", "id": "custom:1"}]
    assert forbidden_calls == []
    assert set(manager.collectors) == {"custom"}

