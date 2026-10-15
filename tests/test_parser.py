from datetime import date
from types import SimpleNamespace

import pytest
import httpx
from openai import APIStatusError, APITimeoutError

from app import parser as parser_module
from app.parser import FailureReason, OpenAIParser, ParseFailure, TaskProposal, get_parser


def test_provider_configuration(monkeypatch):
    made = []

    def fake_client(**kwargs):
        made.append(kwargs)
        return object()

    monkeypatch.setattr(parser_module, "OpenAI", fake_client)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    parser = get_parser()
    assert parser.provider == "openrouter"
    assert parser.model == "test/model"
    assert made[0]["timeout"] == 20.0
    assert made[0]["max_retries"] == 0


def test_missing_key_disables_client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_parser().client is None


def test_structured_proposal_decoding():
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"title":"Report","tags":[]} ', refusal=None))]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: completion)))
    parser = OpenAIParser("openai", "test", client)
    assert parser.propose("report", date(2026, 10, 12)) == TaskProposal(title="Report", tags=[])


def test_timeout_maps_to_controlled_failure():
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(APITimeoutError(request=None)))
        )
    )
    with pytest.raises(ParseFailure) as error:
        OpenAIParser("openai", "test", client).propose("x", date.today())
    assert error.value.reason == FailureReason.TIMEOUT


@pytest.mark.parametrize(
    "status,reason",
    [(429, FailureReason.RATE_LIMITED), (503, FailureReason.PROVIDER_UNAVAILABLE)],
)
def test_http_failures_map_to_controlled_reasons(status, reason):
    request = httpx.Request("POST", "https://example.test")
    response = httpx.Response(status, request=request)
    failure = APIStatusError("provider error", response=response, body=None)
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(failure))
        )
    )
    with pytest.raises(ParseFailure) as error:
        OpenAIParser("openai", "test", client).propose("x", date.today())
    assert error.value.reason == reason
