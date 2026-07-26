from src.processors.pain_detector import (
    analyze_item,
    clean_text,
    detect_pain_signals,
    filter_items_with_pain,
)


def test_clean_text_removes_html():
    text = "<p>This is <b>frustrating</b>.</p>"

    result = clean_text(text)

    assert result == "this is frustrating ."


def test_detects_manual_and_repetitive_work():
    text = (
        "Every day I manually copy and paste "
        "the same information."
    )

    signals = detect_pain_signals(text)

    assert "manual_work" in signals
    assert "repetitive_work" in signals


def test_detects_time_waste():
    text = (
        "This process is time-consuming "
        "and takes hours."
    )

    signals = detect_pain_signals(text)

    assert "time_waste" in signals


def test_text_without_pain_returns_empty():
    text = "Python 3.15 release notes are available."

    signals = detect_pain_signals(text)

    assert signals == {}


def test_analyze_item_adds_metadata():
    item = {
        "id": 1,
        "title": "This manual process is frustrating",
    }

    analyzed_item = analyze_item(item)

    assert analyzed_item["has_pain_signal"] is True
    assert len(analyzed_item["pain_categories"]) >= 1
    assert "pain_signals" in analyzed_item


def test_filter_items_with_pain():
    items = [
        {
            "id": 1,
            "title": "This repetitive task is annoying",
        },
        {
            "id": 2,
            "title": "New database version released",
        },
    ]

    filtered_items = filter_items_with_pain(items)

    assert len(filtered_items) == 1
    assert filtered_items[0]["id"] == 1
