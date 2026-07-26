from src.processors.opportunity_scorer import (
    calculate_confidence_score,
    calculate_engagement_score,
    calculate_market_score,
    calculate_opportunity_score,
    calculate_pain_score,
    calculate_urgency_score,
    classify_opportunity,
    score_opportunities,
    score_opportunity,
)


def build_item():
    return {
        "id": "test-1",
        "source": "github",
        "title": (
            "Urgent: automate repetitive manual workflow"
        ),
        "description": (
            "Our company team spends hours manually "
            "copying customer data. We need a tool "
            "or API to automate this broken process."
        ),
        "url": "https://example.com/item/1",
        "published_at": "2026-07-26T10:00:00Z",
        "score": 50,
        "comments": 20,
        "views": 1000,
        "pain_categories": [
            "manual_work",
            "repetitive_work",
            "time_waste",
        ],
        "pain_signals": {
            "manual_work": ["manually"],
            "repetitive_work": ["repetitive"],
            "time_waste": ["spends hours"],
        },
    }


def test_calculate_pain_score():
    score = calculate_pain_score(build_item())

    assert score > 0
    assert score <= 100


def test_calculate_urgency_score():
    score = calculate_urgency_score(build_item())

    assert score > 0
    assert score <= 100


def test_calculate_engagement_score():
    score = calculate_engagement_score(build_item())

    assert score > 0
    assert score <= 100


def test_calculate_market_score():
    score = calculate_market_score(build_item())

    assert score > 0
    assert score <= 100


def test_calculate_confidence_score():
    score = calculate_confidence_score(build_item())

    assert score >= 80
    assert score <= 100


def test_calculate_opportunity_score():
    score = calculate_opportunity_score(
        pain_score=100,
        urgency_score=100,
        engagement_score=100,
        market_score=100,
        confidence_score=100,
    )

    assert score == 100


def test_classify_opportunity():
    assert classify_opportunity(90) == "critical"
    assert classify_opportunity(70) == "high"
    assert classify_opportunity(50) == "medium"
    assert classify_opportunity(30) == "low"
    assert classify_opportunity(10) == "very_low"


def test_score_opportunity_adds_scores():
    result = score_opportunity(build_item())

    assert "pain_score" in result
    assert "urgency_score" in result
    assert "engagement_score" in result
    assert "market_score" in result
    assert "confidence_score" in result
    assert "opportunity_score" in result
    assert "opportunity_level" in result


def test_score_opportunities_orders_results():
    high_item = build_item()

    low_item = {
        "id": "test-2",
        "source": "stackoverflow",
        "title": "Small issue",
        "description": "There is a problem.",
        "url": "https://example.com/item/2",
        "pain_categories": ["frustration"],
        "pain_signals": {
            "frustration": ["problem"],
        },
    }

    result = score_opportunities(
        [low_item, high_item]
    )

    assert len(result) == 2

    assert (
        result[0]["opportunity_score"]
        >= result[1]["opportunity_score"]
    )


def test_empty_item_does_not_fail():
    result = score_opportunity({})

    assert result["opportunity_score"] >= 0
    assert result["opportunity_score"] <= 100
