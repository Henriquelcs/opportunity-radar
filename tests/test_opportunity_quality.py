from src.quality.opportunity_quality import (
    calculate_relevance,
    filter_opportunities,
    is_noise_opportunity,
    is_query_relevant,
    query_tokens,
)


def test_removes_agents_radar():
    items = [
        {
            "source": "github",
            "title": "Spreadsheet automation report",
            "url": (
                "https://github.com/user/"
                "agents-radar/issues/10"
            ),
        }
    ]

    assert filter_opportunities(
        items,
        "spreadsheet automation",
    ) == []


def test_removes_automatic_digest():
    assert is_noise_opportunity(
        {
            "title": (
                "OpenClaw Ecosystem Digest "
                "2026-07-26"
            )
        }
    )


def test_removes_duplicate_url():
    items = [
        {
            "source": "github",
            "title": (
                "Automate spreadsheet workflow"
            ),
            "body": (
                "Spreadsheet automation."
            ),
            "url": (
                "https://github.com/test/"
                "repo/issues/1"
            ),
        },
        {
            "source": "github",
            "title": (
                "Spreadsheet automation duplicate"
            ),
            "body": (
                "Automate spreadsheet tasks."
            ),
            "url": (
                "https://github.com/test/"
                "repo/issues/1?source=search"
            ),
        },
    ]

    assert len(
        filter_opportunities(
            items,
            "spreadsheet automation",
        )
    ) == 1


def test_derived_fields_cannot_create_relevance():
    item = {
        "source": "github",
        "title": (
            "Native Apple subscription manager"
        ),
        "body": (
            "Manage Apple subscriptions."
        ),
        "pain_summary": (
            "spreadsheet automation"
        ),
        "problem": (
            "spreadsheet automation"
        ),
    }

    assert not is_query_relevant(
        item,
        "spreadsheet automation",
    )


def test_removes_apple_subscription_manager():
    item = {
        "source": "github",
        "title": (
            "Spec: Native Apple "
            "subscription manager"
        ),
        "body": (
            "Subscriptions, payments and "
            "mobile purchase management."
        ),
    }

    assert not is_query_relevant(
        item,
        "spreadsheet automation",
    )


def test_removes_unrelated_support_ticket():
    item = {
        "source": "stackoverflow",
        "title": (
            "GitHub account has been flagged"
        ),
        "body": (
            "Support ticket is unanswered."
        ),
    }

    assert not is_query_relevant(
        item,
        "customer support automation",
    )


def test_removes_generic_client_manager():
    item = {
        "source": "github",
        "title": (
            "Build WhatsApp client "
            "request manager"
        ),
        "body": (
            "Manage messages and products."
        ),
    }

    assert not is_query_relevant(
        item,
        "customer support automation",
    )


def test_keeps_google_sheets_automation():
    item = {
        "source": "github",
        "title": (
            "Configure Google Sheets "
            "writeback automation"
        ),
        "body": (
            "Automate spreadsheet updates "
            "and data synchronization."
        ),
    }

    assert is_query_relevant(
        item,
        "spreadsheet automation",
    )


def test_keeps_customer_support_automation():
    item = {
        "source": "github",
        "title": (
            "Automate customer support tickets"
        ),
        "body": (
            "Customer support agents need "
            "ticket automation."
        ),
    }

    assert is_query_relevant(
        item,
        "customer support automation",
    )


def test_keeps_repetitive_data_entry():
    item = {
        "source": "github",
        "title": (
            "Automate repetitive data entry"
        ),
        "body": (
            "Data entry is repetitive "
            "and requires manual work."
        ),
    }

    assert is_query_relevant(
        item,
        "repetitive data entry",
    )


def test_removes_repetitive_algorithm_input():
    item = {
        "source": "github",
        "title": (
            "Algorithm is slow on "
            "repetitive input"
        ),
        "body": (
            "Collision chain performance."
        ),
    }

    assert not is_query_relevant(
        item,
        "repetitive data entry",
    )


def test_keeps_python_automation_error():
    item = {
        "source": "stackoverflow",
        "title": (
            "Python automation script error"
        ),
        "body": (
            "The Python workflow fails "
            "during automation."
        ),
    }

    assert is_query_relevant(
        item,
        "python automation error",
    )


def test_normalizes_aliases():
    tokens = query_tokens(
        "Excel client ticket automation"
    )

    assert "spreadsheet" in tokens
    assert "customer" in tokens
    assert "support" in tokens
    assert "automation" in tokens


def test_calculates_full_relevance():
    item = {
        "title": (
            "Spreadsheet automation"
        ),
        "body": (
            "Automate spreadsheet work."
        ),
    }

    assert calculate_relevance(
        item,
        "spreadsheet automation",
    ) == 1.0

def test_keeps_single_generic_query_after_pain_analysis():
    item = {
        "source": "github",
        "title": "Manual reconciliation workflow",
        "body": (
            "The process is repetitive "
            "and consumes significant time."
        ),
        "pain_types": [
            "manual_work",
            "repetitive_work",
        ],
    }

    assert is_query_relevant(
        item,
        "automation",
    )

def test_blocks_repetitive_input_even_when_body_mentions_data_entry():
    item = {
        "source": "github",
        "title": (
            "Algorithm is slow on repetitive input"
        ),
        "body": (
            "The benchmark contains data entry "
            "structures and repetitive values."
        ),
    }

    assert not is_query_relevant(
        item,
        "repetitive data entry",
    )


def test_blocks_data_issue_without_entry_in_title():
    item = {
        "source": "github",
        "title": "Dead links in data directory",
        "body": (
            "The repetitive data entry process "
            "contains broken links."
        ),
    }

    assert not is_query_relevant(
        item,
        "repetitive data entry",
    )


def test_requires_customer_and_support_in_title():
    item = {
        "source": "github",
        "title": "WhatsApp client request manager",
        "body": (
            "Automate customer support workflows."
        ),
    }

    assert not is_query_relevant(
        item,
        "customer support automation",
    )

