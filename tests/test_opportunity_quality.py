from src.quality.opportunity_quality import (
    calculate_relevance,
    filter_opportunities,
    is_noise_opportunity,
    is_query_relevant,
    query_tokens,
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


def test_removes_job_radar_batch():
    item = {
        "source": "github",
        "title": (
            "Job Radar batch — "
            "2026-07-26"
        ),
        "url": (
            "https://github.com/example/"
            "jobs/issues/30"
        ),
    }

    assert is_noise_opportunity(item)


def test_removes_duplicate_url():
    items = [
        {
            "source": "github",
            "title": "Manual workflow",
            "url": (
                "https://github.com/example/"
                "project/issues/1"
            ),
        },
        {
            "source": "github",
            "title": "Manual workflow duplicate",
            "url": (
                "https://github.com/example/"
                "project/issues/1?ref=search"
            ),
        },
    ]

    result = filter_opportunities(
        items,
        query="manual workflow",
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
            "opportunity_score": 90,
        }
    ]

    assert filter_opportunities(
        items,
        query="spreadsheet automation",
    ) == []


def test_removes_unrelated_high_score_issue():
    items = [
        {
            "source": "github",
            "title": (
                "Native Apple subscription manager"
            ),
            "body": (
                "Build subscriptions for iOS."
            ),
            "url": (
                "https://github.com/example/"
                "project/issues/3"
            ),
            "opportunity_score": 99,
        }
    ]

    assert filter_opportunities(
        items,
        query="spreadsheet automation",
    ) == []


def test_removes_unrelated_stackoverflow_question():
    items = [
        {
            "source": "stackoverflow",
            "title": (
                "GitHub account has been flagged"
            ),
            "body": (
                "My ticket has not been answered."
            ),
            "url": (
                "https://stackoverflow.com/"
                "questions/123/example"
            ),
            "opportunity_score": 60,
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
                "Automate spreadsheet data entry"
            ),
            "body": (
                "The current spreadsheet workflow "
                "requires repetitive manual entry."
            ),
            "url": (
                "https://github.com/example/"
                "project/issues/4"
            ),
            "opportunity_score": 55,
        }
    ]

    result = filter_opportunities(
        items,
        query="spreadsheet data entry",
    )

    assert len(result) == 1


def test_keeps_relevant_stackoverflow_result():
    items = [
        {
            "source": "stackoverflow",
            "title": (
                "Python automation script fails"
            ),
            "body": (
                "The Python workflow raises an "
                "error during automation."
            ),
            "url": (
                "https://stackoverflow.com/"
                "questions/456/example"
            ),
            "opportunity_score": 40,
        }
    ]

    result = filter_opportunities(
        items,
        query="python automation error",
    )

    assert len(result) == 1


def test_automation_is_not_stopword():
    assert "automation" in query_tokens(
        "spreadsheet automation"
    )


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


def test_requires_multiple_matches_for_long_query():
    unrelated = {
        "title": "Customer portal redesign",
        "body": "New colors and navigation.",
    }

    relevant = {
        "title": (
            "Customer support workflow automation"
        ),
        "body": (
            "Automate customer support tickets."
        ),
    }

    assert not is_query_relevant(
        unrelated,
        "customer support automation",
    )

    assert is_query_relevant(
        relevant,
        "customer support automation",
    )
