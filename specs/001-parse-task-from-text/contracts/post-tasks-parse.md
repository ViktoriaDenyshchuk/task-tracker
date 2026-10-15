# Contract: `POST /tasks/parse`

## Request

`Content-Type: application/json`

```json
{"text":"Здати звіт до п'ятниці, терміново #робота"}
```

`text` — рядок від 1 до 500 символів включно, не порожній і не лише пробільний. Невалідний запит відхиляється FastAPI/Pydantic з HTTP 422 до `get_parser` та без запису.

## Successful model parse

**HTTP 201**

```json
{
  "task": {
    "id": 1,
    "title": "Здати звіт",
    "due_date": "2026-10-16",
    "priority": "high",
    "tags": ["робота"]
  },
  "path": "model",
  "parsed": true
}
```

The saved task is also visible through the existing `GET /tasks` response. Only deterministic, validated values may be saved. Priority is one of `low`, `medium`, `high`; absent priority is `medium`. The date is null or a valid ISO calendar date not earlier than the injected current date. Tags are normalized and deduplicated before save.

## Rules fallback

**HTTP 201**

```json
{
  "task": {
    "id": 2,
    "title": "Вчора треба було здати есе",
    "due_date": null,
    "priority": "medium",
    "tags": []
  },
  "path": "rules_fallback",
  "parsed": false,
  "reason": "invalid_semantics",
  "needs_review": true
}
```

`reason` is the original failure reason, including when the one permitted retry fails. Reasons `timeout` and `rate_limited` each trigger exactly one application retry. `provider_unavailable`, `invalid_structure`, `incomplete`, `refused`, and `invalid_semantics` trigger no retry. The OpenAI SDK client is configured with `timeout=20` seconds and `max_retries=0`, so SDK-internal retries cannot alter this count. Any model failure for otherwise valid input yields the fallback response, never HTTP 500.

Fallback title is the trimmed source text, capped at 200 characters. Fallback due date is extracted only from an explicit `YYYY-MM-DD` token not earlier than `get_today()`; relative dates are not inferred. Priority is `medium`; tags come only from explicit hashtags.

## Dependencies and observable behavior

- `get_parser` from `app/parser.py` supplies the parser and is overrideable through FastAPI dependency overrides.
- `get_today` from `app/clock.py` supplies the current date in `Europe/Kyiv` and is overrideable.
- `GET /tasks`, `POST /tasks`, and `DELETE /tasks/{id}` retain their current request/response behavior.
