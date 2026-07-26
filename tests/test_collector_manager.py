import pytest

from src.collectors.manager import (
    CollectorManager,
)


class SuccessfulCollector:
    def __init__(self, source, items):
        self.source = source
        self.items = items
        self.calls = []

    def collect(self, limit=30, **kwargs):
        self.calls.append(
            {
                "limit": limit,
                "kwargs": kwargs,
            }
        )

        return self.items[:limit]


class FailingCollector:
    def collect(self, limit=30, **kwargs):
        raise RuntimeError("API unavailable")


def test_collects_from_multiple_sources():
    github = SuccessfulCollector(
        "github",
        [
            {
                "id": "github:1",
                "title": "GitHub pain",
                "url": "https://github.com/1",
            }
        ],
    )

    stackoverflow = SuccessfulCollector(
        "stackoverflow",
        [
            {
                "id": "stackoverflow:1",
                "title": "Stack Overflow pain",
                "url": "https://stackoverflow.com/1",
            }
        ],
    )

    manager = CollectorManager(
        collectors={
            "github": github,
            "stackoverflow": stackoverflow,
        }
    )

    result = manager.collect_all(
        limit_per_source=5,
        source_options={
            "github": {
                "language": "python",
            }
        },
    )

    assert result.total_items == 2
    assert result.errors == {}
    assert result.source_counts == {
        "github": 1,
        "stackoverflow": 1,
    }
    assert result.items[0]["source"] == "github"
    assert (
        result.items[1]["source"]
        == "stackoverflow"
    )
    assert github.calls[0]["limit"] == 5
    assert github.calls[0]["kwargs"] == {
        "language": "python"
    }


def test_isolates_collector_failure():
    manager = CollectorManager(
        collectors={
            "github": SuccessfulCollector(
                "github",
                [
                    {
                        "id": "github:1",
                        "title": "Item",
                    }
                ],
            ),
            "producthunt": FailingCollector(),
        }
    )

    result = manager.collect_all()

    assert result.total_items == 1
    assert result.source_counts["github"] == 1
    assert result.source_counts["producthunt"] == 0
    assert "producthunt" in result.errors
    assert "API unavailable" in (
        result.errors["producthunt"]
    )


def test_fail_fast_propagates_exception():
    manager = CollectorManager(
        collectors={
            "producthunt": FailingCollector(),
        }
    )

    with pytest.raises(RuntimeError):
        manager.collect_all(fail_fast=True)


def test_deduplicates_items():
    duplicate_item = {
        "id": "shared:1",
        "title": "Duplicate",
        "url": "https://example.com/shared",
    }

    manager = CollectorManager(
        collectors={
            "source_a": SuccessfulCollector(
                "source_a",
                [duplicate_item],
            ),
            "source_b": SuccessfulCollector(
                "source_b",
                [duplicate_item],
            ),
        }
    )

    result = manager.collect_all()

    assert result.total_items == 1


def test_collect_source_validates_name():
    manager = CollectorManager(
        collectors={
            "github": SuccessfulCollector(
                "github",
                [],
            )
        }
    )

    with pytest.raises(ValueError):
        manager.collect_source("unknown")
