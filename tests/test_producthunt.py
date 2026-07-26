from src.collectors.producthunt import (
    ProductHuntCollector,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))

        if "oauth/token" in url:
            return FakeResponse(
                {
                    "access_token": "access-token",
                    "expires_in": 3600,
                }
            )

        return FakeResponse(
            {
                "data": {
                    "posts": {
                        "edges": [
                            {
                                "node": {
                                    "id": "ph-1",
                                    "name": (
                                        "Automation Radar"
                                    ),
                                    "tagline": (
                                        "Find repetitive "
                                        "workflows"
                                    ),
                                    "description": (
                                        "Detect painful "
                                        "manual work."
                                    ),
                                    "url": (
                                        "https://producthunt.com/"
                                        "posts/automation-radar"
                                    ),
                                    "website": (
                                        "https://example.com"
                                    ),
                                    "createdAt": (
                                        "2026-07-25T10:00:00Z"
                                    ),
                                    "votesCount": 100,
                                    "commentsCount": 15,
                                    "user": {
                                        "username": "builder"
                                    },
                                    "topics": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "name": (
                                                        "Productivity"
                                                    )
                                                }
                                            },
                                            {
                                                "node": {
                                                    "name": (
                                                        "Automation"
                                                    )
                                                }
                                            },
                                        ]
                                    },
                                }
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None,
                        },
                    }
                }
            }
        )


def test_authenticates_and_collects_posts():
    session = FakeSession()

    collector = ProductHuntCollector(
        api_key="api-key",
        api_secret="api-secret",
        session=session,
    )

    items = collector.collect(limit=10)

    assert len(items) == 1
    assert items[0]["id"] == "producthunt:ph-1"
    assert items[0]["source"] == "producthunt"
    assert items[0]["title"] == "Automation Radar"
    assert items[0]["author"] == "builder"
    assert items[0]["score"] == 100
    assert items[0]["comments_count"] == 15
    assert items[0]["tags"] == [
        "Productivity",
        "Automation",
    ]

    token_url, token_options = session.calls[0]

    assert "oauth/token" in token_url
    assert token_options["json"] == {
        "client_id": "api-key",
        "client_secret": "api-secret",
        "grant_type": "client_credentials",
    }

    graphql_url, graphql_options = session.calls[1]

    assert "graphql" in graphql_url
    assert (
        graphql_options["headers"]["Authorization"]
        == "Bearer access-token"
    )
    assert (
        graphql_options["json"]["variables"]["first"]
        == 10
    )


def test_reuses_cached_access_token():
    session = FakeSession()

    collector = ProductHuntCollector(
        api_key="api-key",
        api_secret="api-secret",
        session=session,
    )

    collector.collect(limit=1)
    collector.collect(limit=1)

    token_calls = [
        call
        for call in session.calls
        if "oauth/token" in call[0]
    ]

    assert len(token_calls) == 1


def test_zero_limit_does_not_authenticate():
    session = FakeSession()

    collector = ProductHuntCollector(
        api_key="api-key",
        api_secret="api-secret",
        session=session,
    )

    assert collector.collect(limit=0) == []
    assert session.calls == []
