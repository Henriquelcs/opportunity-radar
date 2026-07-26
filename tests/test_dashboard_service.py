from src.dashboard.service import (
    build_average_scores_by_source,
)
from src.dashboard.service import (
    build_level_distribution,
)
from src.dashboard.service import (
    build_opportunity_table,
)
from src.dashboard.service import (
    build_runs_history,
)
from src.dashboard.service import (
    build_score_breakdown,
)
from src.dashboard.service import (
    build_source_distribution,
)
from src.dashboard.service import (
    calculate_summary,
)
from src.dashboard.service import (
    filter_opportunities,
)
from src.dashboard.service import (
    format_datetime,
)
from src.dashboard.service import (
    normalize_level,
)


def build_opportunities():
    return [
        {
            "id": 1,
            "source": "github",
            "title": "Automate manual workflow",
            "description": (
                "Team copies customer data manually."
            ),
            "url": "https://example.com/1",
            "pain_categories": [
                "manual_work",
            ],
            "pain_score": 80,
            "urgency_score": 70,
            "engagement_score": 60,
            "market_score": 90,
            "confidence_score": 95,
            "opportunity_score": 82,
            "opportunity_level": "critical",
            "last_seen_at": (
                "2026-07-26T10:00:00+00:00"
            ),
        },
        {
            "id": 2,
            "source": "stackoverflow",
            "title": "Repetitive deployment problem",
            "description": (
                "Developers need a better tool."
            ),
            "url": "https://example.com/2",
            "pain_categories": [
                "repetitive_work",
            ],
            "pain_score": 50,
            "urgency_score": 40,
            "engagement_score": 30,
            "market_score": 60,
            "confidence_score": 80,
            "opportunity_score": 55,
            "opportunity_level": "medium",
            "last_seen_at": (
                "2026-07-26T11:00:00+00:00"
            ),
        },
        {
            "id": 3,
            "source": "github",
            "title": "Small usability issue",
            "description": (
                "A minor interface problem."
            ),
            "url": "https://example.com/3",
            "pain_categories": [
                "usability_problem",
            ],
            "pain_score": 20,
            "urgency_score": 10,
            "engagement_score": 10,
            "market_score": 20,
            "confidence_score": 70,
            "opportunity_score": 22,
            "opportunity_level": "very_low",
            "last_seen_at": (
                "2026-07-26T12:00:00+00:00"
            ),
        },
    ]


def build_runs():
    return [
        {
            "id": 10,
            "query": "automation",
            "execution_status": "SUCCESS",
            "collected_count": 100,
            "pain_count": 30,
            "opportunity_count": 20,
            "persisted_count": 20,
            "collection_errors": {},
            "started_at": (
                "2026-07-26T10:00:00+00:00"
            ),
        }
    ]


def test_calculate_summary():
    summary = calculate_summary(
        build_opportunities(),
        build_runs(),
    )

    assert (
        summary["total_opportunities"]
        == 3
    )

    assert (
        summary["average_score"]
        == 53.0
    )

    assert (
        summary["high_potential_count"]
        == 1
    )

    assert summary["source_count"] == 2

    assert (
        summary["last_run_status"]
        == "SUCCESS"
    )


def test_source_distribution():
    result = build_source_distribution(
        build_opportunities()
    )

    github = next(
        item
        for item in result
        if item["source"] == "github"
    )

    assert github["count"] == 2


def test_level_distribution():
    result = build_level_distribution(
        build_opportunities()
    )

    critical = next(
        item
        for item in result
        if item["level"] == "critical"
    )

    assert critical["count"] == 1


def test_average_scores_by_source():
    result = (
        build_average_scores_by_source(
            build_opportunities()
        )
    )

    github = next(
        item
        for item in result
        if item["source"] == "github"
    )

    assert (
        github["average_score"]
        == 52.0
    )


def test_score_breakdown():
    result = build_score_breakdown(
        build_opportunities()
    )

    assert len(result) == 5

    labels = {
        item["dimension"]
        for item in result
    }

    assert "Dor" in labels
    assert "Mercado" in labels


def test_filter_by_source():
    result = filter_opportunities(
        build_opportunities(),
        sources=["github"],
    )

    assert len(result) == 2

    assert all(
        item["source"] == "github"
        for item in result
    )


def test_filter_by_level():
    result = filter_opportunities(
        build_opportunities(),
        levels=["critical"],
    )

    assert len(result) == 1

    assert (
        result[0]["opportunity_level"]
        == "critical"
    )


def test_filter_by_minimum_score():
    result = filter_opportunities(
        build_opportunities(),
        minimum_score=50,
    )

    assert len(result) == 2

    assert (
        result[0]["opportunity_score"]
        == 82
    )


def test_filter_by_search_text():
    result = filter_opportunities(
        build_opportunities(),
        search_text="deployment",
    )

    assert len(result) == 1
    assert result[0]["id"] == 2


def test_build_opportunity_table():
    rows = build_opportunity_table(
        build_opportunities()
    )

    assert len(rows) == 3
    assert rows[0]["Score"] == 82
    assert rows[0]["Nível"] == "Crítica"


def test_build_runs_history():
    history = build_runs_history(
        build_runs()
    )

    assert len(history) == 1

    assert (
        history[0]["collected"]
        == 100
    )

    assert (
        history[0]["status"]
        == "SUCCESS"
    )


def test_normalize_unknown_level():
    assert (
        normalize_level("unknown")
        == "very_low"
    )


def test_format_datetime():
    result = format_datetime(
        "2026-07-26T10:30:00+00:00"
    )

    assert result == "26/07/2026 10:30"
