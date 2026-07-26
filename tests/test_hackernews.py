from src.collectors.hackernews import (
    HackerNewsCollector,
)


def test_limit_must_be_positive():
    collector = HackerNewsCollector()

    try:
        collector.get_top_story_ids(0)

    except ValueError:
        assert True

    else:
        assert False


def test_collect_returns_list():
    collector = HackerNewsCollector()

    items = collector.collect(limit=2)

    assert isinstance(items, list)
    assert len(items) <= 2


def test_collected_item_has_basic_fields():
    collector = HackerNewsCollector()

    items = collector.collect(limit=1)

    assert len(items) == 1

    item = items[0]

    assert "id" in item
    assert "type" in item
