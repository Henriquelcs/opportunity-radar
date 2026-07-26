from src.collectors.github_issues import (
    GitHubIssuesCollector,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def test_collects_and_normalizes_github_issues():
    session = FakeSession(
        {
            "items": [
                {
                    "id": 101,
                    "title": (
                        "Manual workflow is frustrating"
                    ),
                    "body": (
                        "We copy and paste data every day."
                    ),
                    "html_url": (
                        "https://github.com/acme/app/"
                        "issues/10"
                    ),
                    "repository_url": (
                        "https://api.github.com/repos/"
                        "acme/app"
                    ),
                    "user": {"login": "henrique"},
                    "labels": [
                        {"name": "enhancement"},
                        {"name": "automation"},
                    ],
                    "created_at": (
                        "2026-07-25T10:00:00Z"
                    ),
                    "updated_at": (
                        "2026-07-25T11:00:00Z"
                    ),
                    "comments": 4,
                    "score": 1.0,
                    "state": "open",
                }
            ]
        }
    )

    collector = GitHubIssuesCollector(
        token="token",
        session=session,
    )

    items = collector.collect(limit=10)

    assert len(items) == 1
    assert items[0]["id"] == "github:101"
    assert items[0]["source"] == "github"
    assert items[0]["repository"] == "app"
    assert items[0]["author"] == "henrique"
    assert items[0]["comments_count"] == 4
    assert items[0]["tags"] == [
        "enhancement",
        "automation",
    ]

    _, request_options = session.calls[0]

    assert (
        request_options["headers"]["Authorization"]
        == "Bearer token"
    )
    assert request_options["params"]["per_page"] == 10


def test_ignores_pull_requests():
    session = FakeSession(
        {
            "items": [
                {
                    "id": 1,
                    "title": "Issue",
                },
                {
                    "id": 2,
                    "title": "Pull request",
                    "pull_request": {
                        "url": "https://example.com"
                    },
                },
            ]
        }
    )

    collector = GitHubIssuesCollector(
        session=session,
    )

    items = collector.collect(limit=10)

    assert len(items) == 1
    assert items[0]["external_id"] == 1


def test_zero_limit_does_not_call_api():
    session = FakeSession({"items": []})

    collector = GitHubIssuesCollector(
        session=session,
    )

    assert collector.collect(limit=0) == []
    assert session.calls == []
