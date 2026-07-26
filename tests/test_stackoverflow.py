from src.collectors.stackoverflow import (
    StackOverflowCollector,
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


def test_collects_stackoverflow_questions():
    session = FakeSession(
        {
            "items": [
                {
                    "question_id": 500,
                    "title": (
                        "How can I automate this "
                        "manual process?"
                    ),
                    "body": (
                        "<p>This task takes hours.</p>"
                    ),
                    "link": (
                        "https://stackoverflow.com/"
                        "questions/500"
                    ),
                    "owner": {
                        "display_name": "Henrique",
                        "reputation": 120,
                    },
                    "creation_date": 1760000000,
                    "last_activity_date": 1760000500,
                    "tags": ["python", "automation"],
                    "score": 8,
                    "answer_count": 3,
                    "view_count": 250,
                    "is_answered": True,
                }
            ]
        }
    )

    collector = StackOverflowCollector(
        session=session,
    )

    items = collector.collect(
        limit=20,
        tagged=["python", "automation"],
    )

    assert len(items) == 1
    assert (
        items[0]["id"]
        == "stackoverflow:500"
    )
    assert (
        items[0]["source"]
        == "stackoverflow"
    )
    assert items[0]["author"] == "Henrique"
    assert items[0]["score"] == 8
    assert items[0]["comments_count"] == 3
    assert items[0]["metadata"]["view_count"] == 250
    assert items[0]["tags"] == [
        "python",
        "automation",
    ]

    _, request_options = session.calls[0]
    parameters = request_options["params"]

    assert parameters["pagesize"] == 20
    assert parameters["tagged"] == "python;automation"
    assert parameters["filter"] == "withbody"


def test_zero_limit_does_not_call_api():
    session = FakeSession({"items": []})

    collector = StackOverflowCollector(
        session=session,
    )

    assert collector.collect(limit=0) == []
    assert session.calls == []
