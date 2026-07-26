from src.quality.opportunity_quality import (
    calculate_relevance,
    filter_opportunities,
    is_noise_opportunity,
)


def test_removes_agents_radar_repository():
    items = [
        {
            "source": "github",
            "title": "AI ecosystem report",
            "url": (
                "https://github.com/example/"
                "agents-radar/issues/10"
            ),
            "opportunity_score": 90,
        }
    ]

    assert filter_opportunities(
        items,
        query="automation",
    ) == []


def test_removes_automatic_digest():
    item = {
        "source": "github",
        "title": (
            "OpenClaw Ecosystem Digest "
            "2026-07-26"
        ),
        "url": (
            "https://github.com/example/"
            "project/issues/20"
        ),
    }

    assert is_noise_opportunity(item)


def test_removes_duplicate_url():
    items = [
        {
            "source": "github",
            "title": "Manual work",
            "url": (
                "https://github.com/example/"
                "project/issues/1"
            ),
        },
        {
            "source": "github",
            "title": "Manual work duplicate",
            "url": (
                "https://github.com/example/"
                "project/issues/1?ref=search"
            ),
        },
    ]

    result = filter_opportunities(
        items,
        query="manual work",
    )

    assert len(result) == 1


def test_removes_unrelated_meta_issue():
    items = [
        {
            "source": "github",
            "title": (
                "PRD: Rebuild internal "
                "authentication architecture"
            ),
            "body": "OAuth and session handling.",
            "url": (
                "https://github.com/example/"
                "project/issues/2"
            ),
            "opportunity_score": 50,
        }
    ]

    assert filter_opportunities(
        items,
        query="spreadsheet automation",
    ) == []


def test_keeps_relevant_github_issue():
    items = [
        {
            "source": "github",
            "title": (
                "Feature request: automate "
                "spreadsheet data entry"
            ),
            "url": (
                "https://github.com/example/"
                "project/issues/3"
            ),
            "opportunity_score": 55,
        }
    ]

    result = filter_opportunities(
        items,
        query="spreadsheet data entry",
    )

    assert len(result) == 1


def test_keeps_stackoverflow_result():
    items = [
        {
            "source": "stackoverflow",
            "title": (
                "How can I process these "
                "records automatically?"
            ),
            "url": (
                "https://stackoverflow.com/"
                "questions/123/example"
            ),
            "opportunity_score": 40,
        }
    ]

    result = filter_opportunities(
        items,
        query="python automation error",
    )

    assert len(result) == 1


def test_calculates_query_relevance():
    item = {
        "title": (
            "Automate repetitive "
            "spreadsheet data entry"
        )
    }

    relevance = calculate_relevance(
        item,
        "spreadsheet data entry",
    )

    assert relevance == 1.0
