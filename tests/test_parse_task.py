from datetime import date, datetime as DateTime

import pytest
from fastapi.testclient import TestClient

from app.clock import get_today
from app import clock as clock_module
from app.main import app
from app.parser import FailureReason, ParseFailure, TaskProposal, get_parser
from app.storage import TaskStore, get_store


class StubParser:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def propose(self, text, today):
        self.calls.append((text, today))
        outcome = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def setup_client(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_today] = lambda: date(2026, 10, 12)
    yield store
    app.dependency_overrides.clear()


def client_with(parser):
    app.dependency_overrides[get_parser] = lambda: parser
    return TestClient(app)


def test_success_parse_is_persisted_and_visible(setup_client):
    parser = StubParser(TaskProposal(title=" Submit report ", due_date="2026-10-16", priority="high", tags=["Work"]))
    with client_with(parser) as client:
        response = client.post("/tasks/parse", json={"text": "Submit report Friday #work"})
        assert response.status_code == 201
        body = response.json()
        assert body == {
            "task": {"id": 1, "title": "Submit report", "due_date": "2026-10-16", "priority": "high", "tags": ["work"]},
            "path": "model", "parsed": True,
        }
        assert client.get("/tasks").json() == [body["task"]]
    assert parser.calls == [("Submit report Friday #work", date(2026, 10, 12))]


@pytest.mark.parametrize("text", ["", "   ", "x" * 501])
def test_invalid_input_does_not_call_parser_or_save(setup_client, text):
    parser = StubParser(TaskProposal(title="never"))
    with client_with(parser) as client:
        response = client.post("/tasks/parse", json={"text": text})
        assert response.status_code == 422
        assert client.get("/tasks").json() == []
    assert parser.calls == []


def test_five_hundred_characters_allowed(setup_client):
    parser = StubParser(ParseFailure(FailureReason.REFUSED))
    with client_with(parser) as client:
        assert client.post("/tasks/parse", json={"text": "x" * 500}).status_code == 201


def test_fallback_truncates_title_and_ignores_past_date(setup_client):
    parser = StubParser(ParseFailure(FailureReason.REFUSED))
    with client_with(parser) as client:
        body = client.post("/tasks/parse", json={"text": "x" * 201 + " 2026-10-11"}).json()
    assert len(body["task"]["title"]) == 200
    assert body["task"]["due_date"] is None


def test_clock_uses_europe_kyiv(monkeypatch):
    class FixedDateTime:
        @classmethod
        def now(cls, timezone):
            assert str(timezone) == "Europe/Kyiv"
            return DateTime(2026, 10, 12)

    monkeypatch.setattr(clock_module, "datetime", FixedDateTime)
    assert get_today() == date(2026, 10, 12)


def test_defaults_and_fallback_fields(setup_client):
    parser = StubParser(TaskProposal(title="Read notes"))
    with client_with(parser) as client:
        body = client.post("/tasks/parse", json={"text": "Read notes"}).json()
    assert body["task"]["due_date"] is None
    assert body["task"]["priority"] == "medium"

    fallback = StubParser(ParseFailure(FailureReason.REFUSED))
    with client_with(fallback) as client:
        body = client.post("/tasks/parse", json={"text": "  Do it 2026-10-13 #Work #work "}).json()
    assert body["task"]["title"] == "Do it 2026-10-13 #Work #work"
    assert body["task"]["due_date"] == "2026-10-13"
    assert body["task"]["tags"] == ["work"]
    assert body["needs_review"] is True


@pytest.mark.parametrize("reason,retries", [(FailureReason.TIMEOUT, 2), (FailureReason.RATE_LIMITED, 2),
                                              (FailureReason.PROVIDER_UNAVAILABLE, 1), (FailureReason.INVALID_STRUCTURE, 1),
                                              (FailureReason.INCOMPLETE, 1), (FailureReason.REFUSED, 1),
                                              (FailureReason.INVALID_SEMANTICS, 1)])
def test_failure_retry_policy(setup_client, reason, retries):
    parser = StubParser(ParseFailure(reason), ParseFailure(FailureReason.PROVIDER_UNAVAILABLE))
    with client_with(parser) as client:
        response = client.post("/tasks/parse", json={"text": "Write notes"})
    assert response.status_code == 201
    assert response.json()["reason"] == reason.value
    assert response.json()["path"] == "rules_fallback"
    assert response.json()["parsed"] is False
    assert response.json()["needs_review"] is True
    assert len(parser.calls) == retries


@pytest.mark.parametrize("proposal", [
    TaskProposal(title=" "), TaskProposal(title="x" * 201), TaskProposal(title="bad", due_date="2026-02-30"),
    TaskProposal(title="bad", due_date="2026-10-11"), TaskProposal(title="bad", priority="critical"),
    TaskProposal(title="bad", tags=[""]), TaskProposal(title="bad", tags=["a", "b", "c", "d", "e", "f"]),
])
def test_invalid_model_fields_fallback(setup_client, proposal):
    with client_with(StubParser(proposal)) as client:
        response = client.post("/tasks/parse", json={"text": "Use fallback"})
    assert response.json()["path"] == "rules_fallback"
    assert response.json()["reason"] == "invalid_semantics"


def test_empty_model_priority_falls_back_as_invalid_semantics(setup_client):
    parser = StubParser(TaskProposal(title="Use fallback", priority=""))
    with client_with(parser) as client:
        response = client.post("/tasks/parse", json={"text": "Use fallback"})

    assert response.status_code == 201
    assert response.json()["path"] == "rules_fallback"
    assert response.json()["reason"] == "invalid_semantics"
    assert response.json()["parsed"] is False
    assert response.json()["needs_review"] is True
    assert response.json()["task"]["priority"] == "medium"


def test_tag_normalization_and_legacy_routes(setup_client):
    parser = StubParser(TaskProposal(title="Task", tags=[" Work ", "work", "HOME"]))
    with client_with(parser) as client:
        parsed = client.post("/tasks/parse", json={"text": "Task #Work"}).json()
        assert parsed["task"]["tags"] == ["work", "home"]
        manual = client.post("/tasks", json={"title": "Manual"})
        assert manual.status_code == 201
        assert manual.json()["priority"] == "medium"
        assert client.get("/tasks").status_code == 200
        assert client.delete(f"/tasks/{manual.json()['id']}").status_code == 204
        assert client.delete("/tasks/999").status_code == 404
