"""Model-backed task parser and its injectable application boundary."""

from __future__ import annotations

import json
import os
from datetime import date
from enum import StrEnum
from typing import Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class FailureReason(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_STRUCTURE = "invalid_structure"
    INCOMPLETE = "incomplete"
    REFUSED = "refused"
    INVALID_SEMANTICS = "invalid_semantics"


class ParseFailure(Exception):
    def __init__(self, reason: FailureReason):
        self.reason = reason
        super().__init__(reason.value)


class TaskProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    due_date: str | None = None
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)


class TaskParser(Protocol):
    def propose(self, text: str, today: date) -> TaskProposal: ...


class OpenAIParser:
    def __init__(self, provider: str, model: str, client: OpenAI | None):
        self.provider = provider
        self.model = model
        self.client = client

    def propose(self, text: str, today: date) -> TaskProposal:
        if self.client is None:
            raise ParseFailure(FailureReason.PROVIDER_UNAVAILABLE)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                timeout=20.0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract one task as JSON with title, due_date (YYYY-MM-DD or null), "
                            "priority (low, medium, high or null), and tags (string array). "
                            "Only return these fields. Today is " + today.isoformat() + "."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
            )
        except APITimeoutError as exc:
            raise ParseFailure(FailureReason.TIMEOUT) from exc
        except APIStatusError as exc:
            reason = FailureReason.RATE_LIMITED if exc.status_code == 429 else FailureReason.PROVIDER_UNAVAILABLE
            raise ParseFailure(reason) from exc
        except APIConnectionError as exc:
            raise ParseFailure(FailureReason.PROVIDER_UNAVAILABLE) from exc
        except Exception as exc:
            raise ParseFailure(FailureReason.PROVIDER_UNAVAILABLE) from exc

        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message is None:
            raise ParseFailure(FailureReason.INCOMPLETE)
        if choice.message.refusal:
            raise ParseFailure(FailureReason.REFUSED)
        content = choice.message.content
        if not content:
            raise ParseFailure(FailureReason.INCOMPLETE)
        try:
            payload = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ParseFailure(FailureReason.INVALID_STRUCTURE) from exc
        try:
            return TaskProposal.model_validate(payload)
        except ValidationError as exc:
            raise ParseFailure(FailureReason.INVALID_STRUCTURE) from exc


def get_parser() -> TaskParser:
    """Construct the provider parser; tests and evals override this dependency."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = None
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    else:
        raise ValueError("LLM_PROVIDER must be openai or openrouter")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=20.0, max_retries=0) if api_key else None
    return OpenAIParser(provider, model, client)
