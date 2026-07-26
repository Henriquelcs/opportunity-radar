from src.processors.scorer import (
    calculate_engagement_score,
    calculate_opportunity_score,
    calculate_pain_score,
    classify_opportunity,
    rank_opportunities,
    score_item,
)


def test_calculate_pain_score():
    item = {
        "pain_categories": [
            "manual_work",
            "time_waste",
        ]
    }

    assert calculate_pain_score(item) == 40


def test_duplicate_category_is_not_counted_twice():
    item = {
        "pain_categories": [
            "manual_work",
            "manual_work",
        ]
    }

    assert calculate_pain_score(item) == 20


def test_engagement_score_has_maximum_20():
    item = {
        "score": 1000,
        "descendants": 1000,
    }

    assert calculate_engagement_score(item) == 20


def test_opportunity_score_has_maximum_100():
    item = {
        "pain_categories": [
            "manual_work",
            "time_waste",
            "repetitive_work",
            "frustration",
            "missing_solution",
            "problem_report",
        ],
        "score": 1000,
        "descendants": 1000,
    }

    assert calculate_opportunity_score(item) == 100


def test_classify_opportunity():
    assert classify_opportunity(80) == "alta"
    assert classify_opportunity(60) == "media"
    assert classify_opportunity(30) == "baixa"
    assert classify_opportunity(10) == "muito_baixa"


def test_score_item_adds_metadata():
    item = {
        "pain_categories": [
            "manual_work",
        ],
        "score": 50,
        "descendants": 20,
    }

    scored_item = score_item(item)

    assert scored_item["pain_score"] == 20
    assert scored_item["engagement_score"] == 8
    assert scored_item["opportunity_score"] == 28
    assert scored_item["opportunity_level"] == "baixa"


def test_rank_opportunities_orders_highest_first():
    items = [
        {
            "id": 1,
            "pain_categories": [
                "problem_report",
            ],
            "score": 10,
            "descendants": 1,
        },
        {
            "id": 2,
            "pain_categories": [
                "manual_work",
                "time_waste",
            ],
            "score": 100,
            "descendants": 50,
        },
    ]

    ranked_items = rank_opportunities(items)

    assert ranked_items[0]["id"] == 2
    assert (
        ranked_items[0]["opportunity_score"]
        >
        ranked_items[1]["opportunity_score"]
    )
