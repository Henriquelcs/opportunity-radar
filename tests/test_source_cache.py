from __future__ import annotations

from src.cache.source_cache import SourceCache


def item(source: str, external_id: str) -> dict:
    return {
        "source": source,
        "external_id": external_id,
        "title": f"Item {external_id}",
        "description": "manual repetitive workflow",
        "url": f"https://example.com/{external_id}",
    }


def test_snapshot_and_item_cache_are_persistent(tmp_path) -> None:
    path = tmp_path / "cache.db"
    first = SourceCache(path)
    first.save_snapshot("devto", [item("devto", "1")])
    first.upsert_items("hackernews", [item("hackernews", "10")])

    second = SourceCache(path)
    snapshot = second.latest_snapshot("devto")
    assert snapshot is not None
    assert snapshot.item_count == 1
    assert snapshot.items[0]["external_id"] == "1"
    assert second.get_item("hackernews", "10")["title"] == "Item 10"


def test_cooldown_is_persistent(tmp_path) -> None:
    cache = SourceCache(tmp_path / "cache.db")
    cache.set_cooldown("devto", 60, reason="HTTP 429")
    assert cache.cooldown_remaining("devto") > 0
    cache.clear_cooldown("devto")
    assert cache.cooldown_remaining("devto") == 0
